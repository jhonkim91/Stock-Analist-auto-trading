from __future__ import annotations

import os
from collections.abc import MutableMapping, Sequence
from pathlib import Path
from typing import Any

SECRET_LIKE_ENV_NAME_PARTS = (
    "ACCOUNT",
    "APP_KEY",
    "APP_SECRET",
    "CHAT_ID",
    "DATABASE_URL",
    "KEY",
    "SECRET",
    "TOKEN",
    "WEBHOOK",
)


def load_env_file(
    path: Path,
    *,
    allowed_keys: Sequence[str],
    override: bool = False,
    target: MutableMapping[str, str] | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """로컬 env 파일의 allowlist 키만 현재 프로세스용 target에 로드한다."""
    env_target = os.environ if target is None else target
    allowed = set(allowed_keys)
    resolved = path if path.is_absolute() else (project_root or Path.cwd()) / path
    if not resolved.exists():
        return {
            "ok": False,
            "status": "env_file_missing",
            "reason": "ENV_FILE_MISSING",
            "reason_codes": ["ENV_FILE_MISSING"],
            "path": _record_path(resolved, project_root),
            "network_call_performed": False,
            "raw_secret_printed": False,
            "secrets_redacted": True,
        }

    loaded: list[str] = []
    skipped_existing: list[str] = []
    ignored: list[str] = []
    try:
        for raw_line in resolved.read_text(encoding="utf-8").splitlines():
            parsed = parse_env_line(raw_line)
            if parsed is None:
                continue
            key, value = parsed
            if key not in allowed:
                ignored.append(key)
                continue
            if not override and str(env_target.get(key, "")).strip():
                skipped_existing.append(key)
                continue
            env_target[key] = value
            loaded.append(key)
    except OSError:
        return {
            "ok": False,
            "status": "env_file_read_failed",
            "reason": "ENV_FILE_READ_FAILED",
            "reason_codes": ["ENV_FILE_READ_FAILED"],
            "path": _record_path(resolved, project_root),
            "network_call_performed": False,
            "raw_secret_printed": False,
            "secrets_redacted": True,
        }

    ignored_unique = sorted(set(ignored))
    return {
        "ok": True,
        "status": "env_file_loaded",
        "path": _record_path(resolved, project_root),
        "override": override,
        "loaded_keys": public_env_key_names(loaded),
        "skipped_existing_keys": public_env_key_names(skipped_existing),
        "ignored_keys": public_env_key_names(ignored_unique),
        "loaded_count": len(loaded),
        "skipped_existing_count": len(skipped_existing),
        "ignored_count": len(ignored_unique),
        "secret_like_key_names_redacted": True,
        "loaded_secret_like_key_count": secret_like_env_key_count(loaded),
        "skipped_secret_like_key_count": secret_like_env_key_count(skipped_existing),
        "ignored_secret_like_key_count": secret_like_env_key_count(ignored_unique),
        "network_call_performed": False,
        "raw_secret_printed": False,
        "secrets_redacted": True,
    }


def scan_env_file_keys(
    path: Path,
    *,
    key_names: Sequence[str],
    project_root: Path | None = None,
) -> dict[str, Any]:
    """로컬 env 파일에서 지정 key의 존재 여부만 redacted form으로 스캔한다."""
    resolved = path if path.is_absolute() else (project_root or Path.cwd()) / path
    if not resolved.exists():
        return {
            "ok": False,
            "status": "env_file_missing",
            "reason": "ENV_FILE_MISSING",
            "reason_codes": ["ENV_FILE_MISSING"],
            "path": _record_path(resolved, project_root),
            "key_presence": {name: False for name in key_names},
            "configured_count": 0,
            "network_call_performed": False,
            "raw_secret_printed": False,
            "secrets_redacted": True,
            "values_redacted": True,
        }

    key_set = set(key_names)
    presence = {name: False for name in key_names}
    try:
        for raw_line in resolved.read_text(encoding="utf-8").splitlines():
            parsed = parse_env_line(raw_line)
            if parsed is None:
                continue
            key, value = parsed
            if key in key_set and _configured_env_value(value):
                presence[key] = True
    except OSError:
        return {
            "ok": False,
            "status": "env_file_read_failed",
            "reason": "ENV_FILE_READ_FAILED",
            "reason_codes": ["ENV_FILE_READ_FAILED"],
            "path": _record_path(resolved, project_root),
            "key_presence": {name: False for name in key_names},
            "configured_count": 0,
            "network_call_performed": False,
            "raw_secret_printed": False,
            "secrets_redacted": True,
            "values_redacted": True,
        }

    return {
        "ok": True,
        "status": "env_file_scanned",
        "path": _record_path(resolved, project_root),
        "key_presence": presence,
        "configured_count": sum(1 for configured in presence.values() if configured),
        "network_call_performed": False,
        "raw_secret_printed": False,
        "secrets_redacted": True,
        "values_redacted": True,
    }


def parse_env_line(raw_line: str) -> tuple[str, str] | None:
    """한 줄짜리 env 할당식을 key/value로 파싱한다."""
    line = raw_line.strip()
    if not line or line.startswith("#"):
        return None
    if line.lower().startswith("export "):
        line = line[7:].strip()
    if "=" not in line:
        return None
    key, value = line.split("=", 1)
    key = key.strip()
    if not key:
        return None
    return key, strip_env_value(value.strip())


def strip_env_value(value: str) -> str:
    """단순 quoted env value에서 바깥 quote만 제거한다."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def public_env_key_names(keys: Sequence[str]) -> list[str]:
    """secret-like 이름이 아닌 env key만 record에 남긴다."""
    return sorted(key for key in keys if not is_secret_like_env_key_name(key))


def secret_like_env_key_count(keys: Sequence[str]) -> int:
    """secret-like env key 개수를 반환한다."""
    return sum(1 for key in keys if is_secret_like_env_key_name(key))


def is_secret_like_env_key_name(key: str) -> bool:
    """env key 이름이 secret-like인지 판정한다."""
    normalized = key.upper()
    return any(part in normalized for part in SECRET_LIKE_ENV_NAME_PARTS)


def _configured_env_value(value: object) -> bool:
    stripped = str(value or "").strip()
    return bool(stripped and "placeholder" not in stripped.lower())


def _record_path(path: Path, project_root: Path | None) -> str:
    if project_root is None:
        return str(path)
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)
