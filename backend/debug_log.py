from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def _shorten(value: str, limit: int = 1200) -> str:
    value = value or ""
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def response_snapshot(response: Any) -> dict:
    try:
        body = response.text or ""
    except Exception:
        body = ""

    headers = {}
    try:
        headers = {str(key): str(value) for key, value in response.headers.items()}
    except Exception:
        headers = {}

    return {
        "status": getattr(response, "status_code", None),
        "url": getattr(response, "url", ""),
        "headers": headers,
        "body": _shorten(body),
    }


def append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(record, ensure_ascii=False))
        fp.write("\n")
