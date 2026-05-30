"""Stock Analyst 단일 프로세스 진입점.

FastAPI 백엔드가 정적 export된 Next.js UI와 `/api/*`를 동일 오리진에서 서빙한다.
PyInstaller로 패키징하면 이 모듈이 .exe의 진입점이 된다 (Python/Node 설치 불필요).

실행:
    py app_main.py            # 서버 실행 후 브라우저 자동 오픈
    py app_main.py --no-browser
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

# 백엔드 import 이전에 경로/환경을 확정한다.
from backend.app.core.paths import DATA_DIR, ensure_runtime_dirs

HOST = os.getenv("STOCK_ANALYST_HOST", "127.0.0.1")
PORT = int(os.getenv("STOCK_ANALYST_PORT", "8000"))
BASE_URL = f"http://{HOST}:{PORT}"


def _configure_runtime() -> None:
    """런타임 디렉터리를 만들고 DB 경로를 cwd 독립 절대경로로 고정한다."""
    ensure_runtime_dirs()
    # 설정의 기본 DB url은 cwd 상대경로(sqlite:///./backend/data/app.db)다.
    # .exe는 임의 폴더에서 실행될 수 있으므로 절대경로로 덮어쓴다.
    # 사용자가 DATABASE_URL을 명시하면 그 값을 존중한다(setdefault).
    db_path = (DATA_DIR / "app.db").resolve().as_posix()
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{db_path}")


def _wait_and_open_browser(base_url: str) -> None:
    """/health가 응답하면 대시보드를 브라우저로 연다."""
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=2) as response:
                if response.status < 500:
                    webbrowser.open(base_url + "/")
                    return
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.5)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stock Analyst 단일 프로세스 실행")
    parser.add_argument("--no-browser", action="store_true", help="브라우저를 자동으로 열지 않습니다.")
    parser.add_argument("--host", default=HOST, help=f"바인딩 호스트 (기본 {HOST})")
    parser.add_argument("--port", type=int, default=PORT, help=f"바인딩 포트 (기본 {PORT})")
    args = parser.parse_args(argv)

    _configure_runtime()

    # 경로/환경 확정 후에 앱을 import 한다 (import 시점에 DB 엔진이 생성됨).
    import uvicorn

    from backend.app.main import app

    base_url = f"http://{args.host}:{args.port}"
    if not args.no_browser:
        threading.Thread(target=_wait_and_open_browser, args=(base_url,), daemon=True).start()

    print(f"[stock-analyst] 실행 중: {base_url}/  (종료: Ctrl+C)")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
