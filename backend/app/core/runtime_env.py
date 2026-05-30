"""프로그램 내에서 입력한 환경변수(자격증명/토글)를 영속화한다.

- 사용자가 UI에서 설정한 값은 exe 옆 runtime_env.json에 사용자별로 저장된다.
- 시작 시 load_persisted_env()로 global 설정을 os.environ에 반영한다.
- 인증된 API 요청 중에는 해당 user_id 설정을 os.environ에 overlay한다.
- allowlist(앱 설정용 prefix/이름)만 허용해 임의 시스템 env 조작을 막는다.
- 민감 값은 마스킹해서만 노출한다.
"""

from __future__ import annotations

import contextvars
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

_CURRENT_USER_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar("runtime_env_current_user_id", default=None)
_BASE_ENV = dict(os.environ)


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


def _normalize_user_id(user_id: str | None) -> str | None:
    if user_id is None:
        return None
    normalized = str(user_id).strip()
    return normalized or None


def set_current_user(user_id: str | None) -> contextvars.Token[str | None]:
    """현재 요청의 사용자 ID를 context-local로 설정한다."""
    return _CURRENT_USER_ID.set(_normalize_user_id(user_id))


def reset_current_user(token: contextvars.Token[str | None]) -> None:
    """set_current_user() 이전 context 상태로 되돌린다."""
    _CURRENT_USER_ID.reset(token)


def current_user_id() -> str | None:
    """현재 요청 context의 사용자 ID를 반환한다."""
    return _CURRENT_USER_ID.get()


def scope_label(user_id: str | None = None) -> str:
    """환경 값 적용 범위 라벨을 반환한다."""
    return "user" if _normalize_user_id(user_id) or current_user_id() else "process"


def _empty_store() -> dict[str, Any]:
    return {"global": {}, "users": {}}


def _string_map(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    return {str(k).strip().upper(): str(v) for k, v in raw.items() if isinstance(k, str) and str(k).strip()}


def _read_store() -> dict[str, Any]:
    if not RUNTIME_ENV_FILE.exists():
        return _empty_store()
    try:
        data = json.loads(RUNTIME_ENV_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_store()
    if not isinstance(data, dict):
        return _empty_store()

    if "global" in data or "users" in data:
        users_raw = data.get("users", {})
        users: dict[str, dict[str, str]] = {}
        if isinstance(users_raw, dict):
            for user_id, values in users_raw.items():
                normalized_user_id = _normalize_user_id(str(user_id))
                if normalized_user_id:
                    users[normalized_user_id] = _string_map(values)
        return {"global": _string_map(data.get("global", {})), "users": users}

    # v0.24 이전의 flat runtime_env.json은 global scope로 자동 승격한다.
    return {"global": _string_map(data), "users": {}}


def _write_store(data: dict[str, Any]) -> None:
    ensure_runtime_dirs()
    RUNTIME_ENV_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        if os.name != "nt":
            os.chmod(RUNTIME_ENV_FILE, 0o600)
    except OSError:
        pass


def _scope_values(user_id: str | None = None) -> tuple[dict[str, str], dict[str, str]]:
    store = _read_store()
    global_values = {k: v for k, v in store["global"].items() if is_allowed_key(k)}
    normalized_user_id = _normalize_user_id(user_id) or current_user_id()
    user_values = {}
    if normalized_user_id:
        user_values = {k: v for k, v in store["users"].get(normalized_user_id, {}).items() if is_allowed_key(k)}
    return global_values, user_values


def _managed_keys(store: dict[str, Any]) -> set[str]:
    keys = {key for key in store["global"] if is_allowed_key(key)}
    for values in store["users"].values():
        keys.update(key for key in values if is_allowed_key(key))
    return keys


def load_persisted_env(user_id: str | None = None) -> int:
    """저장된 환경변수를 os.environ에 반영한다(허용 키만). 반영 개수를 반환."""
    return activate_persisted_env(user_id)


def activate_persisted_env(user_id: str | None = None) -> int:
    """global 값 위에 현재 사용자 값을 overlay하고 이전 사용자 저장값은 제거한다."""
    applied = 0
    store = _read_store()
    normalized_user_id = _normalize_user_id(user_id) or current_user_id()
    global_values, user_values = _scope_values(user_id)
    active_values = {**global_values, **user_values}
    for key in _managed_keys(store):
        if key in active_values:
            os.environ[key] = active_values[key]
            applied += 1
        elif normalized_user_id is None and key in _BASE_ENV:
            os.environ[key] = _BASE_ENV[key]
        else:
            os.environ.pop(key, None)
    return applied


def get_persisted_raw(user_id: str | None = None) -> dict[str, str]:
    """저장 파일의 원본 값(허용 키만)."""
    global_values, user_values = _scope_values(user_id)
    return {**global_values, **user_values}


def get_effective(key: str, user_id: str | None = None) -> str | None:
    """현재 프로세스에서 유효한 값(os.environ)."""
    upper = key.strip().upper()
    _, user_values = _scope_values(user_id)
    if user_id or current_user_id():
        if upper in user_values:
            return user_values[upper]
    return os.environ.get(upper)


def is_persisted(key: str, user_id: str | None = None) -> bool:
    """현재 scope 저장소에 key가 직접 저장되어 있는지 확인한다."""
    upper = key.strip().upper()
    normalized_user_id = _normalize_user_id(user_id) or current_user_id()
    store = _read_store()
    if normalized_user_id:
        return upper in store["users"].get(normalized_user_id, {})
    return upper in store["global"]


def set_persisted_env(key: str, value: str, user_id: str | None = None) -> bool:
    """허용 키 하나를 저장 파일에 기록하고 os.environ에 반영한다."""
    key = key.strip().upper()
    if not is_allowed_key(key):
        return False
    store = _read_store()
    normalized_user_id = _normalize_user_id(user_id) or current_user_id()
    if normalized_user_id:
        store.setdefault("users", {}).setdefault(normalized_user_id, {})[key] = value
    else:
        store.setdefault("global", {})[key] = value
    _write_store(store)
    os.environ[key] = value
    return True


def delete_persisted_env(key: str, user_id: str | None = None) -> bool:
    """저장 파일에서 키를 제거한다(os.environ은 유지하지 않음)."""
    key = key.strip().upper()
    store = _read_store()
    normalized_user_id = _normalize_user_id(user_id) or current_user_id()
    target = store.setdefault("global", {})
    if normalized_user_id:
        target = store.setdefault("users", {}).setdefault(normalized_user_id, {})
    if key in target:
        del target[key]
        _write_store(store)
        os.environ.pop(key, None)
        activate_persisted_env(normalized_user_id)
        return True
    return False


def masked_snapshot(keys: list[str], user_id: str | None = None) -> list[dict[str, Any]]:
    """주어진 키들의 (마스킹된) 현재값/설정여부를 반환한다."""
    rows: list[dict[str, Any]] = []
    normalized_user_id = _normalize_user_id(user_id) or current_user_id()
    store = _read_store()
    persisted = store["users"].get(normalized_user_id, {}) if normalized_user_id else store["global"]
    for key in keys:
        upper = key.strip().upper()
        effective = get_effective(upper, normalized_user_id)
        rows.append(
            {
                "key": upper,
                "configured": bool(effective),
                "persisted": upper in persisted,
                "sensitive": is_sensitive_key(upper),
                "masked_value": mask_value(upper, effective),
                "scope": "user" if normalized_user_id else "global",
            }
        )
    return rows
