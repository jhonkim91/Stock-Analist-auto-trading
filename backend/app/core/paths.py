from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    """PyInstaller로 패키징된 단일 실행 파일(.exe)에서 실행 중인지 여부."""
    return bool(getattr(sys, "frozen", False))


def _bundle_root() -> Path:
    """번들된 읽기 전용 리소스(config, frontend export 등)의 루트.

    PyInstaller는 데이터 파일을 `sys._MEIPASS` 임시 폴더에 풀어둔다.
    개발 환경에서는 소스 트리 루트를 사용한다.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parents[3]


def _runtime_root() -> Path:
    """쓰기 가능한 런타임 산출물(DB, reports)을 저장할 영속 루트.

    frozen 실행 파일에서 `_MEIPASS`는 임시·읽기 전용이므로,
    실행 파일과 같은 폴더를 영속 데이터 위치로 사용한다.
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


# 번들 리소스 경로 (읽기 전용)
PROJECT_ROOT = _bundle_root()
BACKEND_ROOT = PROJECT_ROOT / "backend"
CONFIG_DIR = BACKEND_ROOT / "config"

# 런타임 산출물 경로 (쓰기 가능, 영속)
RUNTIME_ROOT = _runtime_root()
DATA_DIR = RUNTIME_ROOT / "backend" / "data"
REPORT_DIR = RUNTIME_ROOT / "backend" / "reports"

# 로그인/환경설정 영속 파일 (쓰기 가능, exe 옆)
AUTH_FILE = DATA_DIR / "users.json"
AUTH_SECRET_FILE = DATA_DIR / "auth_secret.key"
RUNTIME_ENV_FILE = DATA_DIR / "runtime_env.json"


def ensure_runtime_dirs() -> None:
    """런타임 산출물 디렉터리를 생성한다."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
