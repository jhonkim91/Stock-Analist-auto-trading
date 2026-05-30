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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
FRONTEND_EXPORT_DIR = FRONTEND_DIR / "out"
APP_ENTRYPOINT = PROJECT_ROOT / "app_main.py"
SPEC_FILE = PROJECT_ROOT / "stock_analyst.spec"
VENV_DIR = PROJECT_ROOT / ".venv"
VENV_BIN_DIR = VENV_DIR / ("Scripts" if os.name == "nt" else "bin")
VENV_PYTHON = VENV_BIN_DIR / ("python.exe" if os.name == "nt" else "python")
STATE_PATH = PROJECT_ROOT / ".launcher" / "state.json"
APP_HOST = "127.0.0.1"
APP_PORT = 8000
APP_BASE_URL = f"http://{APP_HOST}:{APP_PORT}"
APP_LOG_PATH = PROJECT_ROOT / ".launcher" / "app.log"
APP_ERR_PATH = PROJECT_ROOT / ".launcher" / "app.err.log"


class LauncherError(RuntimeError):
    """launcher가 fail-closed로 중단해야 하는 실행 오류."""


def now_iso() -> str:
    """UTC ISO timestamp를 반환한다."""
    return datetime.now(timezone.utc).isoformat()


def npm_command() -> str | None:
    """Windows에서는 npm.cmd를 우선하고, 없으면 npm 실행 파일을 찾는다."""
    return shutil.which("npm.cmd") or shutil.which("npm")


def app_command(python_path: str | Path | None = None) -> list[str]:
    """단일 프로세스 앱(app_main.py) 실행 명령을 구성한다."""
    python = str(python_path or VENV_PYTHON)
    return [python, str(APP_ENTRYPOINT), "--host", APP_HOST, "--port", str(APP_PORT)]


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


def _state_pid(state: dict[str, Any]) -> int | None:
    raw_pid = state.get("app_pid")
    return raw_pid if isinstance(raw_pid, int) else None


def launcher_owns_port(state: dict[str, Any]) -> bool:
    """열린 포트가 launcher state의 살아있는 child process에 속하는지 판단한다."""
    return (
        state.get("app_host") == APP_HOST
        and state.get("app_port") == APP_PORT
        and process_exists(_state_pid(state))
    )


def ensure_port_available(state: dict[str, Any]) -> str:
    """unknown 프로세스가 고정 포트를 점유하면 fail-closed로 중단한다."""
    if not is_port_open(APP_HOST, APP_PORT):
        return "free"
    if launcher_owns_port(state):
        return "launcher-owned"
    raise LauncherError(
        f"알 수 없는 프로세스가 고정 포트를 사용 중입니다: {APP_PORT}. 먼저 해당 서버를 종료하세요."
    )


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
    """로컬 Python/Node 의존성을 설치하고 Next.js 정적 export를 생성한다."""
    if not VENV_PYTHON.exists():
        run_checked([sys.executable, "-m", "venv", str(VENV_DIR)], cwd=PROJECT_ROOT)
    run_checked([str(VENV_PYTHON), "-m", "pip", "install", "-r", "requirements.txt"], cwd=PROJECT_ROOT)

    npm = require_npm()
    run_checked([npm, "install"], cwd=FRONTEND_DIR)
    # output: "export" 설정으로 `next build`가 frontend/out 정적 사이트를 생성한다.
    # 단일 프로세스는 동일 오리진에서 API를 서빙하므로 API base를 빈 값으로 강제한다.
    # 실제 환경변수는 frontend/.env.local보다 우선하므로 개발용 override를 덮어쓴다.
    build_env = os.environ.copy()
    build_env["NEXT_PUBLIC_API_BASE_URL"] = ""
    run_checked([npm, "run", "build"], cwd=FRONTEND_DIR, env=build_env)
    if not FRONTEND_EXPORT_DIR.is_dir():
        raise LauncherError(f"정적 export 생성에 실패했습니다: {FRONTEND_EXPORT_DIR}")


def setup_required() -> bool:
    """run 전에 setup이 필요한 대표 산출물 누락 여부를 확인한다."""
    return not (
        VENV_PYTHON.exists()
        and (FRONTEND_DIR / "node_modules").exists()
        and (FRONTEND_EXPORT_DIR / "index.html").exists()
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


def run_server() -> None:
    """단일 프로세스 앱을 백그라운드로 실행하고 상태를 기록한다 (브라우저는 앱이 연다)."""
    if setup_required():
        print("[launcher] 필요한 산출물이 없어 setup을 먼저 실행합니다.")
        setup_environment()

    state = load_state()
    if ensure_port_available(state) == "launcher-owned":
        print(f"[launcher] 이미 실행 중입니다: {APP_BASE_URL}/")
        return

    app = start_process(
        app_command(),
        cwd=PROJECT_ROOT,
        env=os.environ.copy(),
        stdout_path=APP_LOG_PATH,
        stderr_path=APP_ERR_PATH,
    )
    try:
        wait_for_http(f"{APP_BASE_URL}/health", timeout_seconds=60, process=app)
    except Exception:
        terminate_process(app.pid)
        raise

    save_state(
        {
            "started_at": now_iso(),
            "project_root": str(PROJECT_ROOT),
            "app_pid": app.pid,
            "app_host": APP_HOST,
            "app_port": APP_PORT,
            "app_url": f"{APP_BASE_URL}/",
            "app_log": str(APP_LOG_PATH),
        }
    )
    print(f"[launcher] 실행 완료: {APP_BASE_URL}/")


def terminate_process(pid: int | None) -> None:
    """PID 하나와 그 child process를 종료한다."""
    if not process_exists(pid):
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False)
        return
    os.kill(int(pid), signal.SIGTERM)


def stop_server() -> None:
    """launcher state에 기록된 child process만 종료한다."""
    state = load_state()
    if not state:
        print("[launcher] 종료할 launcher state가 없습니다.")
        return
    pid = _state_pid(state)
    if pid:
        print(f"[launcher] app 종료 시도: PID {pid}")
        terminate_process(pid)
    remove_state()
    print("[launcher] 종료 완료")


def build_exe() -> None:
    """PyInstaller로 단일 실행 파일(.exe)을 빌드한다."""
    if setup_required():
        print("[launcher] .exe 빌드 전 setup(의존성/정적 export)을 먼저 실행합니다.")
        setup_environment()
    run_checked(
        [str(VENV_PYTHON), "-m", "pip", "install", "pyinstaller"],
        cwd=PROJECT_ROOT,
    )
    if not SPEC_FILE.exists():
        raise LauncherError(f"PyInstaller spec 파일이 없습니다: {SPEC_FILE}")
    run_checked(
        [str(VENV_PYTHON), "-m", "PyInstaller", "--noconfirm", str(SPEC_FILE)],
        cwd=PROJECT_ROOT,
    )
    exe_name = "StockAnalyst.exe" if os.name == "nt" else "StockAnalyst"
    exe_path = PROJECT_ROOT / "dist" / exe_name
    print(f"[launcher] .exe 빌드 완료: {exe_path}")


def check_environment() -> int:
    """현재 단일 프로그램 실행 준비 상태를 점검한다."""
    failures: list[str] = []

    def report(label: str, status: str, detail: str) -> None:
        print(f"[{status}] {label}: {detail}")
        if status == "FAIL":
            failures.append(label)

    report("python", "OK", sys.executable)
    report("requirements", "OK" if (PROJECT_ROOT / "requirements.txt").exists() else "FAIL", "requirements.txt")
    report("app entrypoint", "OK" if APP_ENTRYPOINT.exists() else "FAIL", str(APP_ENTRYPOINT))
    report("venv", "OK" if VENV_PYTHON.exists() else "WARN", str(VENV_PYTHON))
    npm = npm_command()
    report("npm", "OK" if npm else "WARN", npm or "Node.js npm not found (정적 export 빌드 시 필요)")
    report("frontend package", "OK" if (FRONTEND_DIR / "package.json").exists() else "FAIL", "frontend/package.json")
    report("frontend node_modules", "OK" if (FRONTEND_DIR / "node_modules").exists() else "WARN", "frontend/node_modules")
    report("frontend export", "OK" if (FRONTEND_EXPORT_DIR / "index.html").exists() else "WARN", str(FRONTEND_EXPORT_DIR))
    report("pyinstaller spec", "OK" if SPEC_FILE.exists() else "WARN", str(SPEC_FILE))
    try:
        status = ensure_port_available(load_state())
        report("app port", "OK", f"{APP_PORT} {status}")
    except LauncherError as exc:
        report("port", "FAIL", str(exc))
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    """launcher CLI parser를 구성한다."""
    parser = argparse.ArgumentParser(description="Stock Analyst 단일 프로그램 launcher")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check", help="실행 준비 상태를 점검합니다.")
    subparsers.add_parser("setup", help="로컬 의존성을 설치하고 정적 프론트엔드를 빌드합니다.")
    subparsers.add_parser("run", help="단일 프로세스 앱을 실행합니다.")
    subparsers.add_parser("stop", help="launcher가 띄운 프로세스를 종료합니다.")
    subparsers.add_parser("build-exe", help="PyInstaller로 단일 실행 파일(.exe)을 빌드합니다.")
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
            run_server()
            return 0
        if args.command == "stop":
            stop_server()
            return 0
        if args.command == "build-exe":
            build_exe()
            return 0
    except LauncherError as exc:
        print(f"[launcher] 실패: {exc}", file=sys.stderr)
        return 1
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
