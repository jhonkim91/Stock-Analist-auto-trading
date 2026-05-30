"""로컬 데스크톱용 단순 로그인.

- 사용자(ID/PW)는 JSON 파일(users.json)로 관리한다.
- 비밀번호는 PBKDF2-HMAC-SHA256으로 해시해 저장한다(평문 저장 안 함).
- 토큰은 서버 비밀키로 HMAC 서명한 만료 토큰이라 재시작에도 유효하다.
- 표준 라이브러리만 사용한다(추가 의존성/패키징 부담 없음).

opt-in 정책: 사용자(users.json)가 없으면 인증을 강제하지 않는다(테스트/초기 상태 호환).
사용자가 한 명이라도 생기면 그때부터 /api/* 호출에 토큰이 필요하다.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any

from backend.app.core.paths import AUTH_FILE, AUTH_SECRET_FILE, ensure_runtime_dirs

_PBKDF2_ITERATIONS = 200_000
_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 30  # 30일


# --------------------------------------------------------------- password hash
def hash_password(password: str) -> str:
    """PBKDF2-HMAC-SHA256 해시 문자열을 만든다."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """저장된 해시와 비밀번호가 일치하는지 상수시간 비교한다."""
    try:
        algorithm, iterations_text, salt_hex, digest_hex = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, AttributeError):
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, expected)


# --------------------------------------------------------------- user store
def _read_store() -> dict[str, Any]:
    if not AUTH_FILE.exists():
        return {"users": []}
    try:
        data = json.loads(AUTH_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"users": []}
    if not isinstance(data, dict) or not isinstance(data.get("users"), list):
        return {"users": []}
    return data


def _write_store(store: dict[str, Any]) -> None:
    ensure_runtime_dirs()
    AUTH_FILE.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")
    _restrict_permissions(AUTH_FILE)


def _restrict_permissions(path) -> None:
    """가능하면 소유자만 읽기/쓰기로 권한을 좁힌다(POSIX). Windows는 무시."""
    try:
        if os.name != "nt":
            os.chmod(path, 0o600)
    except OSError:
        pass


def auth_configured() -> bool:
    """사용자가 한 명이라도 등록되어 있으면 True(=인증 강제)."""
    return len(_read_store().get("users", [])) > 0


def list_user_ids() -> list[str]:
    return [str(user.get("id")) for user in _read_store().get("users", []) if user.get("id")]


def _find_user(store: dict[str, Any], user_id: str) -> dict[str, Any] | None:
    for user in store.get("users", []):
        if str(user.get("id")) == user_id:
            return user
    return None


def add_user(user_id: str, password: str) -> bool:
    """신규 사용자를 추가한다. 이미 있으면 False."""
    user_id = user_id.strip()
    if not user_id or not password:
        return False
    store = _read_store()
    if _find_user(store, user_id) is not None:
        return False
    store.setdefault("users", []).append(
        {
            "id": user_id,
            "password_hash": hash_password(password),
            "created_at": _now_iso(),
        }
    )
    _write_store(store)
    return True


def verify_user(user_id: str, password: str) -> bool:
    user = _find_user(_read_store(), user_id.strip())
    if user is None:
        return False
    return verify_password(password, str(user.get("password_hash", "")))


def change_password(user_id: str, old_password: str, new_password: str) -> bool:
    store = _read_store()
    user = _find_user(store, user_id.strip())
    if user is None or not new_password:
        return False
    if not verify_password(old_password, str(user.get("password_hash", ""))):
        return False
    user["password_hash"] = hash_password(new_password)
    _write_store(store)
    return True


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# --------------------------------------------------------------- token (HMAC)
def _secret() -> bytes:
    """서버 서명 비밀키(없으면 생성·저장)."""
    if AUTH_SECRET_FILE.exists():
        try:
            return bytes.fromhex(AUTH_SECRET_FILE.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            pass
    ensure_runtime_dirs()
    key = secrets.token_bytes(32)
    AUTH_SECRET_FILE.write_text(key.hex(), encoding="utf-8")
    _restrict_permissions(AUTH_SECRET_FILE)
    return key


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64u_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def issue_token(user_id: str, ttl_seconds: int = _TOKEN_TTL_SECONDS) -> str:
    payload = {"sub": user_id, "exp": int(time.time()) + ttl_seconds, "iat": int(time.time())}
    body = _b64u(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64u(signature)}"


def verify_token(token: str | None) -> str | None:
    """토큰이 유효하면 사용자 ID를 반환, 아니면 None."""
    if not token:
        return None
    token = token.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    parts = token.split(".")
    if len(parts) != 2:
        return None
    body, signature = parts
    expected = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest()
    try:
        provided = _b64u_decode(signature)
    except (ValueError, Exception):  # noqa: BLE001
        return None
    if not hmac.compare_digest(expected, provided):
        return None
    try:
        payload = json.loads(_b64u_decode(body))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    sub = payload.get("sub")
    return str(sub) if sub else None
