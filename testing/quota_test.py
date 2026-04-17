#!/usr/bin/env python3
import argparse
import json
import time
from datetime import datetime
from pathlib import Path
import sys
from typing import Any, Optional

import requests

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.quota import parse_quota_usage


QUOTA_USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"


def as_dict(value: Any) -> Optional[dict]:
    return value if isinstance(value, dict) else None


def read_number(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def read_number_field(record: Optional[dict], *keys: str) -> Optional[float]:
    if not record:
        return None
    for key in keys:
        value = read_number(record.get(key))
        if value is not None:
            return value
    return None


def clamp_percent(value: Optional[float]) -> int:
    if value is None:
        return 0
    if value <= 1:
        return round(value * 100)
    return max(0, min(100, round(value)))


def read_window(raw: Any) -> dict:
    record = as_dict(raw)
    if not record:
        return {"present": False}

    used_percent = read_number_field(record, "used_percent", "usedPercent")
    remaining_percent = read_number_field(record, "remaining_percent", "remainingPercent")
    direct_percentage = read_number_field(record, "percentage", "percent")
    remaining = read_number_field(record, "remaining", "requests_left", "requestsLeft")
    limit = read_number_field(record, "limit", "requests_limit", "requestsLimit")

    reset_at = read_number_field(record, "reset_at", "resetAt", "reset_time", "resetTime")
    reset_after = read_number_field(
        record,
        "reset_after_seconds",
        "resetAfterSeconds",
        "reset_after",
        "resetAfter",
    )

    window_minutes = read_number_field(
        record,
        "window_minutes",
        "windowMinutes",
        "duration_minutes",
        "durationMinutes",
    )
    window_seconds = read_number_field(
        record,
        "limit_window_seconds",
        "limitWindowSeconds",
        "window_seconds",
        "windowSeconds",
        "duration_seconds",
        "durationSeconds",
    )

    effective_window_minutes = (
        window_minutes
        if window_minutes is not None
        else window_seconds / 60
        if window_seconds is not None
        else None
    )

    percentage = None
    if remaining_percent is not None:
        percentage = clamp_percent(remaining_percent)
    elif direct_percentage is not None:
        percentage = clamp_percent(direct_percentage)
    elif used_percent is not None:
        percentage = clamp_percent(100 - used_percent * 100 if used_percent <= 1 else 100 - used_percent)
    elif remaining is not None and limit is not None and limit > 0:
        percentage = clamp_percent((remaining / limit) * 100)

    reset_time = None
    if reset_at is not None:
        reset_time = int(reset_at / 1000) if reset_at > 1_000_000_000_000 else int(reset_at)
    elif reset_after is not None:
        reset_time = int(time.time() + reset_after)

    return {
        "present": any(
            value is not None
            for value in [percentage, reset_time, remaining, limit, window_seconds]
        ),
        "percentage": percentage,
        "resetTime": reset_time,
        "requestsLeft": remaining,
        "requestsLimit": limit,
        "windowMinutes": effective_window_minutes,
        "windowSeconds": window_seconds,
    }


def resolve_rate_limit_windows(rate_limit: Optional[dict], plan_type: str = "") -> dict:
    if not rate_limit:
        return {}

    plan = plan_type.lower()

    primary = read_window(
        as_dict(rate_limit.get("primary_window"))
        or as_dict(rate_limit.get("primaryWindow"))
    )
    secondary = read_window(
        as_dict(rate_limit.get("secondary_window"))
        or as_dict(rate_limit.get("secondaryWindow"))
    )

    windows = [w for w in [primary, secondary] if w.get("present")]
    if not windows:
        return {}

    if "free" in plan:
        return {
            "monthly": primary if primary.get("present") else secondary
        }

    sorted_windows = sorted(windows, key=lambda w: w.get("windowMinutes") or 0)

    hourly = next(
        (
            w for w in sorted_windows
            if isinstance(w.get("windowMinutes"), (int, float))
            and 0 < w["windowMinutes"] <= 360
        ),
        None,
    )

    weekly = next(
        (
            w for w in sorted_windows
            if isinstance(w.get("windowMinutes"), (int, float))
            and 10080 <= w["windowMinutes"] < 43200
        ),
        None,
    )

    monthly = next(
        (
            w for w in sorted_windows
            if isinstance(w.get("windowMinutes"), (int, float))
            and w["windowMinutes"] >= 43200
        ),
        None,
    )

    return {
        "hourly": hourly,
        "weekly": weekly,
        "monthly": monthly or (sorted_windows[0] if not hourly and not weekly else None),
    }


def format_reset_time(ts: Optional[int]) -> str:
    if not ts:
        return "-"
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def summarize_window(name: str, window: Optional[dict]) -> None:
    if not window or not window.get("present"):
        print(f"{name}: no data")
        return

    left = window.get("requestsLeft")
    limit = window.get("requestsLimit")
    requests = f"{left:g}/{limit:g}" if left is not None and limit is not None else "-"

    print(f"{name}:")
    print(f"  remaining percent : {window.get('percentage', '-') }%")
    print(f"  requests          : {requests}")
    print(f"  window minutes    : {window.get('windowMinutes', '-')}")
    print(f"  reset time        : {format_reset_time(window.get('resetTime'))}")


def fetch_quota(access_token: str, account_id: Optional[str] = None) -> dict:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    if account_id:
        headers["ChatGPT-Account-Id"] = account_id

    response = requests.get(QUOTA_USAGE_URL, headers=headers, timeout=30)

    if not response.ok:
        raise RuntimeError(
            f"Quota request failed: {response.status_code} {response.reason}\n"
            f"{response.text[:1000]}"
        )

    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual Codex quota usage test")
    parser.add_argument("--access-token", required=True, help="ChatGPT/Codex access token")
    parser.add_argument("--account-id", help="Optional ChatGPT account id")
    parser.add_argument("--raw", action="store_true", help="Print raw JSON response")
    args = parser.parse_args()

    raw = fetch_quota(args.access_token, args.account_id)
    summary = parse_quota_usage(raw)

    if args.raw:
        print(json.dumps(raw, indent=2, ensure_ascii=False))
        return

    plan_type = str(raw.get("plan_type") or raw.get("planType") or "").lower()
    rate_limit = as_dict(raw.get("rate_limit")) or as_dict(raw.get("rateLimit"))
    windows = resolve_rate_limit_windows(rate_limit, plan_type)

    code_review_rate_limit = (
        as_dict(raw.get("code_review_rate_limit"))
        or as_dict(raw.get("codeReviewRateLimit"))
        or as_dict(raw.get("code_review"))
        or as_dict(raw.get("codeReview"))
    )
    code_review_windows = resolve_rate_limit_windows(code_review_rate_limit)
    code_review = (
        code_review_windows.get("hourly")
        or code_review_windows.get("weekly")
        or read_window(code_review_rate_limit)
    )

    print(f"plan type: {plan_type or '-'}")
    print(f"alive: {summary.get('alive')}")
    print(f"user id: {summary.get('userId') or '-'}")
    print(f"account id: {summary.get('accountId') or '-'}")
    print(f"email: {summary.get('email') or '-'}")
    print()

    summarize_window("5-hour / hourly limit", windows.get("hourly"))
    summarize_window("weekly limit", windows.get("weekly"))
    summarize_window("monthly limit", windows.get("monthly"))
    summarize_window("code review", code_review)

    credits = as_dict(raw.get("credits"))
    if credits:
        print()
        print("credits:")
        print(f"  has credits           : {credits.get('has_credits', credits.get('hasCredits'))}")
        print(f"  unlimited             : {credits.get('unlimited')}")
        print(f"  overage limit reached : {credits.get('overage_limit_reached', credits.get('overageLimitReached'))}")
        print(f"  balance               : {credits.get('balance', '-')}")


if __name__ == "__main__":
    main()
