from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

CONFIRMATION_TOKEN = "CONFIRM_LIVE_CANARY_PHASE20"
REQUIRED_CONFIRMATION_ENV = "LIVE_CANARY_CONFIRMATION"
REQUIRED_REVIEWER_ENV = "LIVE_CANARY_REVIEWER"
REQUIRED_ENVIRONMENT_ENV = "LIVE_CANARY_ENVIRONMENT"
REQUIRED_ROLLBACK_ENV = "LIVE_CANARY_ROLLBACK_READY"
REQUIRED_KILL_SWITCH_ENV = "LIVE_CANARY_KILL_SWITCH_READY"
REQUIRED_MINIMUM_SIZE_ENV = "LIVE_CANARY_MINIMUM_SIZE_CONFIRMED"
REQUIRED_ENVIRONMENT_VALUE = "prod-live-isolated"
DEFAULT_ROLLBACK_RUNBOOK = Path("docs/LIVE_CANARY_RUNBOOK.md")


class LiveCanaryGovernanceService:
    """live canary 실행 전 human/reviewer/env/rollback proof를 fail-closed로 평가한다."""

    def __init__(
        self,
        env: Mapping[str, str] | None = None,
        *,
        project_root: Path | None = None,
        rollback_runbook_path: Path | None = None,
    ) -> None:
        self.env = os.environ if env is None else env
        self.project_root = project_root or Path.cwd()
        self.rollback_runbook_path = rollback_runbook_path or DEFAULT_ROLLBACK_RUNBOOK

    def evaluate(self) -> dict[str, Any]:
        """operator gate와 rollback proof를 raw reviewer 값 없이 반환한다."""
        reviewer = str(self.env.get(REQUIRED_REVIEWER_ENV, "")).strip()
        rollback_runbook = self._rollback_runbook_status()
        operator_gates = {
            "confirmation": self.env.get(REQUIRED_CONFIRMATION_ENV, "") == CONFIRMATION_TOKEN,
            "reviewer_present": bool(reviewer),
            "environment_is_prod_live": self.env.get(REQUIRED_ENVIRONMENT_ENV, "").strip().lower()
            == REQUIRED_ENVIRONMENT_VALUE,
            "rollback_ready": _is_true(self.env.get(REQUIRED_ROLLBACK_ENV, "")),
            "kill_switch_ready": _is_true(self.env.get(REQUIRED_KILL_SWITCH_ENV, "")),
            "minimum_size_confirmed": _is_true(self.env.get(REQUIRED_MINIMUM_SIZE_ENV, "")),
            "rollback_runbook_present": rollback_runbook["present"],
            "rollback_runbook_has_steps": rollback_runbook["has_steps"],
        }
        blockers = [f"{key.upper()}_REQUIRED" for key, passed in operator_gates.items() if not passed]
        return {
            "passed": not blockers,
            "operator_gates": operator_gates,
            "blockers": blockers,
            "reviewer_present": bool(reviewer),
            "reviewer_fingerprint": _fingerprint(reviewer) if reviewer else None,
            "environment_required": REQUIRED_ENVIRONMENT_VALUE,
            "rollback_runbook": rollback_runbook,
            "network_call_performed": False,
            "live_order_created": False,
            "secrets_redacted": True,
        }

    def _rollback_runbook_status(self) -> dict[str, Any]:
        path = self.rollback_runbook_path
        if not path.is_absolute():
            path = self.project_root / path
        exists = path.exists()
        text = path.read_text(encoding="utf-8") if exists else ""
        has_steps = all(marker in text for marker in ("## Rollback 절차", "LIVE_CANARY_ROLLBACK_READY"))
        return {
            "present": exists,
            "has_steps": has_steps,
            "path": str(self.rollback_runbook_path).replace("\\", "/"),
        }


def _is_true(value: str | None) -> bool:
    return bool(value and value.strip().lower() in {"1", "true", "yes", "on"})


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
