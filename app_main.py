"""Stock Analyst 단일 프로세스 진입점 (데스크톱 네이티브 창).

FastAPI 백엔드가 정적 export된 Next.js UI와 `/api/*`를 동일 오리진에서 서빙하고,
pywebview로 네이티브 OS 창(Windows: WebView2)에 띄운다 — 브라우저 탭/콘솔창 없이
일반 Windows 프로그램처럼 동작한다. pywebview가 없거나 `--no-window`면 기본 브라우저로 폴백한다.

PyInstaller로 패키징하면 이 모듈이 .exe의 진입점이 된다 (Python/Node 설치 불필요).

실행:
    py app_main.py                 # 네이티브 창
    py app_main.py --no-window     # 기본 브라우저로 폴백
    py app_main.py --port 8080
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

# 백엔드 import 이전에 경로/환경을 확정한다.
from backend.app.core.paths import DATA_DIR, RUNTIME_ROOT, ensure_runtime_dirs, is_frozen

DEFAULT_HOST = os.getenv("STOCK_ANALYST_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("STOCK_ANALYST_PORT", "8000"))
WINDOW_TITLE = "Stock Analyst"


def _redirect_frozen_output() -> None:
    """windowed .exe(console=False)는 stdout/stderr가 None이라 로깅이 깨질 수 있다.

    frozen이고 표준 스트림이 없으면 exe 옆 로그 파일로 리다이렉트한다.
    """
    if not is_frozen():
        return
    if sys.stdout is not None and sys.stderr is not None:
        return
    log_dir = RUNTIME_ROOT / "backend" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stream = open(log_dir / "app.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115
    sys.stdout = stream
    sys.stderr = stream


def _configure_runtime() -> None:
    """런타임 디렉터리를 만들고 DB 경로를 cwd 독립 절대경로로 고정한다."""
    ensure_runtime_dirs()
    # 설정의 기본 DB url은 cwd 상대경로(sqlite:///./backend/data/app.db)다.
    # .exe는 임의 폴더에서 실행될 수 있으므로 절대경로로 덮어쓴다(명시 env는 존중).
    db_path = (DATA_DIR / "app.db").resolve().as_posix()
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{db_path}")


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((host, port)) == 0


def _resolve_port(host: str, preferred: int) -> int:
    """선호 포트가 사용 중이면 빈 포트를 새로 할당한다(중복 실행에도 견고)."""
    if not _port_in_use(host, preferred):
        return preferred
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _make_server(host: str, port: int):
    """uvicorn Server를 만든다(시그널 핸들러는 메인스레드 밖에서 비활성)."""
    import uvicorn

    from backend.app.main import app

    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None  # 서버를 별도 스레드에서 돌리므로
    return server


def _wait_for_health(base_url: str, timeout_seconds: int = 60) -> bool:
    """/health가 응답하면 True."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=2) as response:
                if response.status < 500:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.4)
    return False


def _load_webview():
    """pywebview 모듈을 반환하거나, 없으면 None."""
    try:
        import webview  # type: ignore

        return webview
    except Exception:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stock Analyst 단일 프로세스 실행 (네이티브 창)")
    parser.add_argument("--no-window", action="store_true", help="네이티브 창 대신 기본 브라우저로 엽니다.")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"바인딩 호스트 (기본 {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"바인딩 포트 (기본 {DEFAULT_PORT})")
    args = parser.parse_args(argv)

    _redirect_frozen_output()
    _configure_runtime()

    host = args.host
    port = _resolve_port(host, args.port)
    base_url = f"http://{host}:{port}"

    server = _make_server(host, port)
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    print(f"[stock-analyst] 서버 시작: {base_url}/")
    if not _wait_for_health(base_url):
        print("[stock-analyst] 서버가 제때 시작되지 않았습니다.", file=sys.stderr)
        server.should_exit = True
        return 1

    webview = None if args.no_window else _load_webview()
    if webview is not None:
        # 네이티브 OS 창 (Windows: WebView2). 메인 스레드에서 블로킹 실행.
        webview.create_window(
            WINDOW_TITLE,
            base_url + "/",
            width=1440,
            height=900,
            min_size=(1024, 680),
        )
        webview.start()
        # 창이 닫히면 서버를 정리한다.
        server.should_exit = True
        return 0

    # 폴백: 기본 브라우저로 열고 프로세스를 유지한다.
    print(f"[stock-analyst] 실행 중(브라우저 모드): {base_url}/  (종료: Ctrl+C)")
    webbrowser.open(base_url + "/")
    try:
        while server_thread.is_alive():
            server_thread.join(1)
    except KeyboardInterrupt:
        server.should_exit = True
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
