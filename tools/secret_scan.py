from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "backend/data",
    "build",
    "dist",
    "node_modules",
}
SKIP_SUFFIXES = {
    ".db",
    ".ico",
    ".jpg",
    ".jpeg",
    ".log",
    ".pdf",
    ".png",
    ".pyc",
    ".sqlite",
    ".webp",
    ".xlsx",
    ".zip",
}


@dataclass(frozen=True)
class SecretFinding:
    path: Path
    line_number: int
    label: str


SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "discord_webhook_url",
        re.compile(r"https://discord\.com/api/webhooks/[0-9]+/[A-Za-z0-9_-]{20,}"),
    ),
    (
        "telegram_bot_token",
        re.compile(r"\b[0-9]{8,10}:[A-Za-z0-9_-]{30,}\b"),
    ),
    (
        "kis_raw_secret",
        re.compile(
            r"(KIS_(APP_KEY|APP_SECRET|ACCESS_TOKEN|REFRESH_TOKEN)\s*[:=]\s*[\"']?"
            r"(?!\*|<|your|placeholder|env|None|null)[A-Za-z0-9._\-]{12,})",
            re.IGNORECASE,
        ),
    ),
    (
        "raw_token_json",
        re.compile(
            r"(access_token|refresh_token)\s*[\"']?\s*:\s*[\"']"
            r"(?!\*\*\*REDACTED\*\*\*)[A-Za-z0-9._\-]{16,}[\"']",
            re.IGNORECASE,
        ),
    ),
    (
        "raw_account_or_chat_id",
        re.compile(r"(account(_no|_number)?|cano|chat_id)\s*[:=]\s*[\"']?-?[0-9]{6,}", re.IGNORECASE),
    ),
)


def candidate_paths(root: Path = ROOT) -> list[Path]:
    """git 기준 non-ignored 파일 목록을 반환하고 git이 없으면 안전한 rglob fallback을 사용한다."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        raw_paths = [root / line.strip() for line in result.stdout.splitlines() if line.strip()]
    except (OSError, subprocess.CalledProcessError):
        raw_paths = [path for path in root.rglob("*") if path.is_file()]
    return [path for path in raw_paths if _should_scan(path, root)]


def scan_paths(paths: Iterable[Path], root: Path = ROOT) -> list[SecretFinding]:
    """파일 내용을 스캔하되 발견 출력에는 실제 secret 값을 포함하지 않는다."""
    findings: list[SecretFinding] = []
    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            for label, pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append(SecretFinding(path=path.relative_to(root), line_number=line_number, label=label))
    return findings


def _should_scan(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    parts = set(relative.parts)
    relative_posix = str(relative).replace("\\", "/")
    if parts & EXCLUDED_PARTS or any(
        relative_posix == excluded or relative_posix.startswith(f"{excluded}/") for excluded in EXCLUDED_PARTS
    ):
        return False
    if path.suffix.lower() in SKIP_SUFFIXES:
        return False
    return path.is_file()


def main() -> int:
    findings = scan_paths(candidate_paths(), ROOT)
    if not findings:
        print("NO_SECRET_FINDINGS")
        return 0
    print("SECRET_FINDINGS")
    for finding in findings:
        print(f"{finding.path}:{finding.line_number}:{finding.label}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
