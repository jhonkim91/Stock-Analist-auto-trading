from __future__ import annotations

import hashlib
import json
from typing import Any


def stable_hash(payload: dict[str, Any]) -> str:
    """설정/요청 payload를 재현 가능한 hash로 변환한다."""
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]
