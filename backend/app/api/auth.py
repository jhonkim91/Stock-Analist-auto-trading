"""로그인/사용자 관리 API (로컬 단일 사용자 위주, JSON 저장)."""

from __future__ import annotations

from fastapi import APIRouter, Header
from pydantic import BaseModel

from backend.app.core import auth

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SetupRequest(BaseModel):
    id: str
    password: str


class LoginRequest(BaseModel):
    id: str
    password: str


class ChangePasswordRequest(BaseModel):
    id: str
    old_password: str
    new_password: str


@router.get("/status")
def auth_status() -> dict[str, object]:
    """인증 설정 여부와 등록된 ID 목록을 반환한다(비밀번호/토큰 없음)."""
    configured = auth.auth_configured()
    return {
        "configured": configured,
        "setup_required": not configured,
        "user_ids": auth.list_user_ids(),
    }


@router.post("/setup")
def auth_setup(payload: SetupRequest) -> dict[str, object]:
    """최초 사용자(ID/PW)를 생성한다. 이미 설정돼 있으면 거부한다."""
    if auth.auth_configured():
        return {"ok": False, "reason": "ALREADY_CONFIGURED"}
    user_id = payload.id.strip()
    if not user_id or not payload.password:
        return {"ok": False, "reason": "ID_AND_PASSWORD_REQUIRED"}
    if not auth.add_user(user_id, payload.password):
        return {"ok": False, "reason": "USER_CREATE_FAILED"}
    token = auth.issue_token(user_id)
    return {"ok": True, "id": user_id, "token": token}


@router.post("/login")
def auth_login(payload: LoginRequest) -> dict[str, object]:
    """ID/PW 검증 후 토큰을 발급한다."""
    user_id = payload.id.strip()
    if not auth.verify_user(user_id, payload.password):
        return {"ok": False, "reason": "INVALID_CREDENTIALS"}
    return {"ok": True, "id": user_id, "token": auth.issue_token(user_id)}


@router.get("/me")
def auth_me(authorization: str | None = Header(default=None)) -> dict[str, object]:
    """토큰이 유효하면 사용자 ID를 반환한다."""
    user_id = auth.verify_token(authorization)
    if user_id is None:
        return {"ok": False, "authenticated": False}
    return {"ok": True, "authenticated": True, "id": user_id}


@router.post("/change-password")
def auth_change_password(payload: ChangePasswordRequest) -> dict[str, object]:
    """기존 비밀번호 확인 후 새 비밀번호로 변경한다."""
    if not auth.change_password(payload.id.strip(), payload.old_password, payload.new_password):
        return {"ok": False, "reason": "CHANGE_FAILED"}
    return {"ok": True, "id": payload.id.strip(), "token": auth.issue_token(payload.id.strip())}
