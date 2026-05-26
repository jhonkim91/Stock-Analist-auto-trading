from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
VENV_DIR = PROJECT_ROOT / ".venv"
VENV_BIN_DIR = VENV_DIR / ("Scripts" if os.name == "nt" else "bin")
VENV_PYTHON = VENV_BIN_DIR / ("python.exe" if os.name == "nt" else "python")
STATE_PATH = FRONTEND_DIR / ".next" / "launcher-state.json"
BUILD_METADATA_PATH = FRONTEND_DIR / ".next" / "launcher-build.json"
BACKEND_HOST = "127.0.0.1"
FRONTEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000
FRONTEND_PORT = 3000
BACKEND_BASE_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}"
FRONTEND_BASE_URL = f"http://{FRONTEND_HOST}:{FRONTEND_PORT}"
DASHBOARD_URL = f"{FRONTEND_BASE_URL}/dashboard"
BACKEND_LOG_PATH = FRONTEND_DIR / ".next" / "launcher-backend.log"
BACKEND_ERR_PATH = FRONTEND_DIR / ".next" / "launcher-backend.err.log"
FRONTEND_LOG_PATH = FRONTEND_DIR / ".next" / "launcher-frontend.log"
FRONTEND_ERR_PATH = FRONTEND_DIR / ".next" / "launcher-frontend.err.log"


class LauncherError(RuntimeError):
    """launcher가 fail-closed로 중단해야 하는 실행 오류."""


def now_iso() -> str:
    """UTC ISO timestamp를 반환한다."""
    return datetime.now(timezone.utc).isoformat()


def npm_command() -> str | None:
    """Windows에서는 npm.cmd를 우선하고, 없으면 npm 실행 파일을 찾는다."""
    return shutil.which("npm.cmd") or shutil.which("npm")


def backend_command(python_path: str | Path | None = None) -> list[str]:
    """FastAPI backend 실행 명령을 구성한다."""
    python = str(python_path or VENV_PYTHON)
    return [
        python,
        "-m",
        "uvicorn",
        "backend.app.main:app",
        "--host",
        BACKEND_HOST,
        "--port",
        str(BACKEND_PORT),
    ]


def frontend_start_command(npm_path: str | Path) -> list[str]:
    """Next.js production frontend 실행 명령을 구성한다."""
    return [
        str(npm_path),
        "run",
        "start",
        "--",
        "--hostname",
        FRONTEND_HOST,
        "--port",
        str(FRONTEND_PORT),
    ]


def frontend_build_env(base_env: dict[str, str] | None = None) -> dict[str, str]:
    """Next.js build/start에서 사용할 API base 환경을 구성한다."""
    env = dict(base_env or os.environ)
    env["NEXT_PUBLIC_API_BASE_URL"] = BACKEND_BASE_URL
    return env


def paper_bot_launcher_enabled() -> bool:
    """paper bot scheduler는 명시 env flag 없이는 launcher에서 시작하지 않는다."""
    return os.getenv("PAPER_BOT_SCHEDULER_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def is_port_open(host: str, port: int, timeout: float = 0.25) -> bool:
    """TCP 포트가 이미 연결 가능한 상태인지 확인한다."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


def process_exists(pid: int | None) -> bool:
    """PID가 현재 실행 중인지 확인한다."""
    if not pid or pid <= 0:
        return False
    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        )
        return str(pid) in result.stdout
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    """launcher state 파일을 읽는다."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_state(state: dict[str, Any], path: Path = STATE_PATH) -> None:
    """launcher child process state를 저장한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def remove_state(path: Path = STATE_PATH) -> None:
    """launcher state 파일을 제거한다."""
    if path.exists():
        path.unlink()


def save_build_metadata(path: Path = BUILD_METADATA_PATH) -> None:
    """launcher가 검증한 frontend build 조건을 기록한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "built_at": now_iso(),
        "next_public_api_base_url": BACKEND_BASE_URL,
        "frontend_port": FRONTEND_PORT,
        "backend_port": BACKEND_PORT,
    }
    path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")


def build_metadata_is_current(path: Path = BUILD_METADATA_PATH) -> bool:
    """현재 frontend build가 launcher 고정 API base로 생성됐는지 확인한다."""
    if not path.exists():
        return False
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        isinstance(metadata, dict)
        and metadata.get("next_public_api_base_url") == BACKEND_BASE_URL
        and metadata.get("frontend_port") == FRONTEND_PORT
        and metadata.get("backend_port") == BACKEND_PORT
    )


def _state_pid(state: dict[str, Any], role: str) -> int | None:
    raw_pid = state.get(f"{role}_pid")
    return raw_pid if isinstance(raw_pid, int) else None


def _state_port(state: dict[str, Any], role: str) -> int | None:
    raw_port = state.get(f"{role}_port")
    return raw_port if isinstance(raw_port, int) else None


def launcher_owns_port(role: str, host: str, port: int, state: dict[str, Any]) -> bool:
    """열린 포트가 launcher state의 살아있는 child process에 속하는지 판단한다."""
    expected_host = state.get(f"{role}_host")
    expected_port = _state_port(state, role)
    expected_pid = _state_pid(state, role)
    return expected_host == host and expected_port == port and process_exists(expected_pid)


def classify_port(role: str, host: str, port: int, state: dict[str, Any]) -> str:
    """포트를 free, launcher-owned, unknown-occupied 중 하나로 분류한다."""
    if not is_port_open(host, port):
        return "free"
    if launcher_owns_port(role, host, port, state):
        return "launcher-owned"
    return "unknown-occupied"


def ensure_ports_available(state: dict[str, Any]) -> dict[str, str]:
    """unknown 프로세스가 고정 포트를 점유하면 fail-closed로 중단한다."""
    statuses = {
        "backend": classify_port("backend", BACKEND_HOST, BACKEND_PORT, state),
        "frontend": classify_port("frontend", FRONTEND_HOST, FRONTEND_PORT, state),
    }
    unknown = [role for role, status in statuses.items() if status == "unknown-occupied"]
    if unknown:
        details = ", ".join(
            f"{role}={BACKEND_PORT if role == 'backend' else FRONTEND_PORT}" for role in unknown
        )
        raise LauncherError(f"알 수 없는 프로세스가 고정 포트를 사용 중입니다: {details}. 먼저 해당 서버를 종료하세요.")
    return statuses


def ensure_complete_launcher_state(statuses: dict[str, str]) -> bool:
    """launcher-owned 실행 상태가 backend/frontend 모두 완전한지 확인한다."""
    running = [role for role, status in statuses.items() if status == "launcher-owned"]
    if not running:
        return False
    if sorted(running) == ["backend", "frontend"]:
        return True
    raise LauncherError("launcher가 일부 프로세스만 실행 중입니다. `py launcher.py stop` 후 다시 실행하세요.")


def require_npm() -> str:
    """npm 실행 파일을 찾고 없으면 명확한 오류를 낸다."""
    npm = npm_command()
    if not npm:
        raise LauncherError("npm 또는 npm.cmd를 찾을 수 없습니다. Node.js를 설치한 뒤 다시 실행하세요.")
    return npm


def run_checked(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    """외부 명령을 실행하고 실패 시 launcher 오류로 변환한다."""
    print(f"[launcher] 실행: {' '.join(command)}")
    try:
        subprocess.check_call(command, cwd=cwd, env=env)
    except subprocess.CalledProcessError as exc:
        raise LauncherError(f"명령이 실패했습니다: {' '.join(command)}") from exc


def setup_environment() -> None:
    """로컬 Python/Node 의존성을 설치하고 Next.js production build를 준비한다."""
    if not VENV_PYTHON.exists():
        run_checked([sys.executable, "-m", "venv", str(VENV_DIR)], cwd=PROJECT_ROOT)
    run_checked([str(VENV_PYTHON), "-m", "pip", "install", "-r", "requirements.txt"], cwd=PROJECT_ROOT)

    npm = require_npm()
    run_checked([npm, "install"], cwd=FRONTEND_DIR)
    run_checked([npm, "run", "build"], cwd=FRONTEND_DIR, env=frontend_build_env())
    save_build_metadata()


def setup_required() -> bool:
    """run 전에 setup이 필요한 대표 산출물 누락 여부를 확인한다."""
    return not (
        VENV_PYTHON.exists()
        and (FRONTEND_DIR / "node_modules").exists()
        and (FRONTEND_DIR / ".next" / "BUILD_ID").exists()
        and build_metadata_is_current()
    )


def wait_for_http(url: str, timeout_seconds: int, process: subprocess.Popen[str] | None = None) -> None:
    """HTTP endpoint가 응답할 때까지 대기한다."""
    deadline = time.monotonic() + timeout_seconds
    last_error: str | None = None
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise LauncherError(f"프로세스가 시작 중 종료되었습니다: {url}")
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
        time.sleep(1)
    raise LauncherError(f"서버 응답 대기 시간이 초과되었습니다: {url} ({last_error})")


def start_process(command: list[str], *, cwd: Path, env: dict[str, str] | None, stdout_path: Path, stderr_path: Path) -> subprocess.Popen[str]:
    """child process를 시작하고 stdout/stderr를 분리 로그로 남긴다."""
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    stdout_file = stdout_path.open("a", encoding="utf-8")
    stderr_file = stderr_path.open("a", encoding="utf-8")
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=stdout_file,
            stderr=stderr_file,
            text=True,
            creationflags=creationflags,
        )
    finally:
        stdout_file.close()
        stderr_file.close()
    return process


def run_servers(no_browser: bool = False) -> None:
    """backend와 frontend를 순서대로 실행하고 dashboard를 연다."""
    if setup_required():
        print("[launcher] 필요한 산출물이 없어 setup을 먼저 실행합니다.")
        setup_environment()

    state = load_state()
    statuses = ensure_ports_available(state)
    if ensure_complete_launcher_state(statuses):
        print(f"[launcher] 이미 실행 중입니다: {DASHBOARD_URL}")
        if not no_browser:
            webbrowser.open(DASHBOARD_URL)
        return

    npm = require_npm()
    backend = start_process(
        backend_command(),
        cwd=PROJECT_ROOT,
        env=os.environ.copy(),
        stdout_path=BACKEND_LOG_PATH,
        stderr_path=BACKEND_ERR_PATH,
    )
    try:
        wait_for_http(f"{BACKEND_BASE_URL}/health", timeout_seconds=45, process=backend)
        frontend = start_process(
            frontend_start_command(npm),
            cwd=FRONTEND_DIR,
            env=frontend_build_env(),
            stdout_path=FRONTEND_LOG_PATH,
            stderr_path=FRONTEND_ERR_PATH,
        )
        try:
            wait_for_http(DASHBOARD_URL, timeout_seconds=90, process=frontend)
        except Exception:
            terminate_process(frontend.pid)
            raise
    except Exception:
        terminate_process(backend.pid)
        raise

    save_state(
        {
            "started_at": now_iso(),
            "project_root": str(PROJECT_ROOT),
            "backend_pid": backend.pid,
            "backend_host": BACKEND_HOST,
            "backend_port": BACKEND_PORT,
            "frontend_pid": frontend.pid,
            "frontend_host": FRONTEND_HOST,
            "frontend_port": FRONTEND_PORT,
            "dashboard_url": DASHBOARD_URL,
            "backend_log": str(BACKEND_LOG_PATH),
            "frontend_log": str(FRONTEND_LOG_PATH),
        }
    )
    print(f"[launcher] 실행 완료: {DASHBOARD_URL}")
    if not no_browser:
        webbrowser.open(DASHBOARD_URL)


def terminate_process(pid: int | None) -> None:
    """PID 하나와 그 child process를 종료한다."""
    if not process_exists(pid):
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False)
        return
    os.kill(int(pid), signal.SIGTERM)


def stop_servers() -> None:
    """launcher state에 기록된 child process만 종료한다."""
    state = load_state()
    if not state:
        print("[launcher] 종료할 launcher state가 없습니다.")
        return
    for role in ("frontend", "backend"):
        pid = _state_pid(state, role)
        if pid:
            print(f"[launcher] {role} 종료 시도: PID {pid}")
            terminate_process(pid)
    remove_state()
    print("[launcher] 종료 완료")


def check_environment() -> int:
    """현재 단일 PC 실행 준비 상태를 점검한다."""
    failures: list[str] = []

    def report(label: str, status: str, detail: str) -> None:
        print(f"[{status}] {label}: {detail}")
        if status == "FAIL":
            failures.append(label)

    report("python", "OK", sys.executable)
    report("requirements", "OK" if (PROJECT_ROOT / "requirements.txt").exists() else "FAIL", "requirements.txt")
    report("venv", "OK" if VENV_PYTHON.exists() else "WARN", str(VENV_PYTHON))
    npm = npm_command()
    report("npm", "OK" if npm else "FAIL", npm or "Node.js npm not found")
    report("frontend package", "OK" if (FRONTEND_DIR / "package.json").exists() else "FAIL", "frontend/package.json")
    report("frontend node_modules", "OK" if (FRONTEND_DIR / "node_modules").exists() else "WARN", "frontend/node_modules")
    report("frontend build", "OK" if (FRONTEND_DIR / ".next" / "BUILD_ID").exists() else "WARN", "frontend/.next/BUILD_ID")
    report("launcher build metadata", "OK" if build_metadata_is_current() else "WARN", str(BUILD_METADATA_PATH))
    report("paper bot scheduler", "OK", "disabled" if not paper_bot_launcher_enabled() else "explicitly enabled")
    try:
        statuses = ensure_ports_available(load_state())
        report("backend port", "OK", f"{BACKEND_PORT} {statuses['backend']}")
        report("frontend port", "OK", f"{FRONTEND_PORT} {statuses['frontend']}")
    except LauncherError as exc:
        report("ports", "FAIL", str(exc))
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    """launcher CLI parser를 구성한다."""
    parser = argparse.ArgumentParser(description="Stock Analyst 단일 PC 실행 launcher")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check", help="실행 준비 상태를 점검합니다.")
    subparsers.add_parser("setup", help="로컬 의존성을 설치하고 frontend를 빌드합니다.")
    run_parser = subparsers.add_parser("run", help="backend/frontend를 실행합니다.")
    run_parser.add_argument("--no-browser", action="store_true", help="브라우저를 자동으로 열지 않습니다.")
    subparsers.add_parser("stop", help="launcher가 띄운 프로세스를 종료합니다.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            return check_environment()
        if args.command == "setup":
            setup_environment()
            return 0
        if args.command == "run":
            run_servers(no_browser=args.no_browser)
            return 0
        if args.command == "stop":
            stop_servers()
            return 0
    except LauncherError as exc:
        print(f"[launcher] 실패: {exc}", file=sys.stderr)
        return 1
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
