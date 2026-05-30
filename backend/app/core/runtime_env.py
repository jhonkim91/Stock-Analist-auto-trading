"""프로그램 내에서 입력한 환경변수(자격증명/토글)를 영속화한다.

- 사용자가 UI에서 설정한 값은 exe 옆 runtime_env.json에 저장된다.
- 시작 시 load_persisted_env()로 os.environ에 반영한다(사용자 설정이 소스 오브 트루스).
- allowlist(앱 설정용 prefix/이름)만 허용해 임의 시스템 env 조작을 막는다.
- 민감 값은 마스킹해서만 노출한다.
"""

from __future__ import annotations

import json
import os
from typing import Any

from backend.app.core.paths import RUNTIME_ENV_FILE, ensure_runtime_dirs

# 앱 설정 env로 허용할 prefix (그 외 시스템 env는 차단)
_ALLOWED_PREFIXES = (
    "KIS_",
    "PAPER_",
    "TELEGRAM_",
    "REPORT_",
    "NOTIFICATION",
    "NOTIFICATIONS",
    "LIVE_",
    "BROKER_",
    "EXECUTION_",
    "DISCORD_",
)
_ALLOWED_EXACT = {"ENABLE_REAL_ORDER"}

# 마스킹 대상 키워드(값을 그대로 노출하지 않음)
_SENSITIVE_PARTS = (
    "SECRET",
    "TOKEN",
    "PASSWORD",
    "APP_KEY",
    "APPKEY",
    "WEBHOOK",
    "CHAT_ID",
    "ACCOUNT",
    "REFRESH",
    "HASHKEY",
)


def is_allowed_key(key: str) -> bool:
    key = key.strip().upper()
    if key in _ALLOWED_EXACT:
        return True
    return any(key.startswith(prefix) for prefix in _ALLOWED_PREFIXES)


def is_sensitive_key(key: str) -> bool:
    upper = key.upper()
    return any(part in upper for part in _SENSITIVE_PARTS)


def mask_value(key: str, value: str | None) -> str:
    if value is None or value == "":
        return ""
    if not is_sensitive_key(key):
        return value
    if len(value) <= 4:
        return "****"
    return f"{value[:3]}{'*' * 6}{value[-2:]}"


def _read_file() -> dict[str, str]:
    if not RUNTIME_ENV_FILE.exists():
        return {}
    try:
        data = json.loads(RUNTIME_ENV_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items() if isinstance(k, str)}


def _write_file(data: dict[str, str]) -> None:
    ensure_runtime_dirs()
    RUNTIME_ENV_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        if os.name != "nt":
            os.chmod(RUNTIME_ENV_FILE, 0o600)
    except OSError:
        pass


def load_persisted_env() -> int:
    """저장된 환경변수를 os.environ에 반영한다(허용 키만). 반영 개수를 반환."""
    applied = 0
    for key, value in _read_file().items():
        if not is_allowed_key(key):
            continue
        os.environ[key] = value
        applied += 1
    return applied


def get_persisted_raw() -> dict[str, str]:
    """저장 파일의 원본 값(허용 키만)."""
    return {k: v for k, v in _read_file().items() if is_allowed_key(k)}


def get_effective(key: str) -> str | None:
    """현재 프로세스에서 유효한 값(os.environ)."""
    return os.environ.get(key.strip().upper())


def set_persisted_env(key: str, value: str) -> bool:
    """허용 키 하나를 저장 파일에 기록하고 os.environ에 반영한다."""
    key = key.strip().upper()
    if not is_allowed_key(key):
        return False
    data = _read_file()
    data[key] = value
    _write_file(data)
    os.environ[key] = value
    return True


def delete_persisted_env(key: str) -> bool:
    """저장 파일에서 키를 제거한다(os.environ은 유지하지 않음)."""
    key = key.strip().upper()
    data = _read_file()
    if key in data:
        del data[key]
        _write_file(data)
        os.environ.pop(key, None)
        return True
    return False


def masked_snapshot(keys: list[str]) -> list[dict[str, Any]]:
    """주어진 키들의 (마스킹된) 현재값/설정여부를 반환한다."""
    rows: list[dict[str, Any]] = []
    persisted = _read_file()
    for key in keys:
        upper = key.strip().upper()
        effective = os.environ.get(upper)
        rows.append(
            {
                "key": upper,
                "configured": bool(effective),
                "persisted": upper in persisted,
                "sensitive": is_sensitive_key(upper),
                "masked_value": mask_value(upper, effective),
            }
        )
    return rows
