from __future__ import annotations

import time
from typing import Any, Dict, Optional


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


def read_window(raw: Any) -> Dict[str, Any]:
    record = as_dict(raw)
    if not record:
        return {"present": False}

    used_percent = read_number_field(record, "used_percent", "usedPercent")
    remaining_percent = read_number_field(record, "remaining_percent", "remainingPercent")
    direct_percentage = read_number_field(record, "percentage", "percent")
    remaining = read_number_field(record, "remaining", "requests_left", "requestsLeft")
    limit = read_number_field(record, "limit", "requests_limit", "requestsLimit")

    reset_at = read_number_field(record, "reset_at", "resetAt", "reset_time", "resetTime")
    reset_after = read_number_field(record, "reset_after_seconds", "resetAfterSeconds", "reset_after", "resetAfter")

    window_minutes = read_number_field(record, "window_minutes", "windowMinutes", "duration_minutes", "durationMinutes")
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
        "present": any(value is not None for value in [percentage, reset_time, remaining, limit, window_seconds]),
        "percentage": percentage,
        "resetTime": reset_time,
        "requestsLeft": remaining,
        "requestsLimit": limit,
        "windowMinutes": effective_window_minutes,
        "windowSeconds": window_seconds,
    }


def resolve_rate_limit_windows(rate_limit: Optional[dict], plan_type: str = "") -> Dict[str, Any]:
    if not rate_limit:
        return {}

    plan = plan_type.lower()

    primary = read_window(as_dict(rate_limit.get("primary_window")) or as_dict(rate_limit.get("primaryWindow")))
    secondary = read_window(as_dict(rate_limit.get("secondary_window")) or as_dict(rate_limit.get("secondaryWindow")))

    windows = [window for window in [primary, secondary] if window.get("present")]
    if not windows:
        return {}

    if "free" in plan:
        return {"monthly": primary if primary.get("present") else secondary}

    sorted_windows = sorted(windows, key=lambda window: window.get("windowMinutes") or 0)
    hourly = next(
        (
            window
            for window in sorted_windows
            if isinstance(window.get("windowMinutes"), (int, float))
            and 0 < window["windowMinutes"] <= 360
        ),
        None,
    )
    weekly = next(
        (
            window
            for window in sorted_windows
            if isinstance(window.get("windowMinutes"), (int, float))
            and 10080 <= window["windowMinutes"] < 43200
        ),
        None,
    )
    monthly = next(
        (
            window
            for window in sorted_windows
            if isinstance(window.get("windowMinutes"), (int, float))
            and window["windowMinutes"] >= 43200
        ),
        None,
    )

    return {"hourly": hourly, "weekly": weekly, "monthly": monthly or (sorted_windows[0] if not hourly and not weekly else None)}


def parse_quota_usage(raw: Any) -> Dict[str, Any]:
    record = as_dict(raw) or {}
    plan_type = str(record.get("plan_type") or record.get("planType") or "").lower()
    rate_limit = as_dict(record.get("rate_limit")) or as_dict(record.get("rateLimit"))
    windows = resolve_rate_limit_windows(rate_limit, plan_type)
    code_review_rate_limit = (
        as_dict(record.get("code_review_rate_limit"))
        or as_dict(record.get("codeReviewRateLimit"))
        or as_dict(record.get("code_review"))
        or as_dict(record.get("codeReview"))
    )
    code_review_windows = resolve_rate_limit_windows(code_review_rate_limit)
    code_review = code_review_windows.get("hourly") or code_review_windows.get("weekly") or read_window(code_review_rate_limit)
    additional_raw = record.get("additional_rate_limits") or record.get("additionalRateLimits")
    additional_limits = additional_raw if isinstance(additional_raw, list) else None
    user_id = str(record.get("user_id") or record.get("userId") or "").strip()
    account_id = str(record.get("account_id") or record.get("accountId") or "").strip()
    email = str(record.get("email") or "").strip()
    credits = as_dict(record.get("credits"))
    spend_control = as_dict(record.get("spend_control")) or as_dict(record.get("spendControl"))
    rate_limit_reached_type = record.get("rate_limit_reached_type") or record.get("rateLimitReachedType")

    alive = bool(user_id and account_id and email and rate_limit)

    return {
        "raw": record,
        "alive": alive,
        "planType": plan_type,
        "userId": user_id,
        "accountId": account_id,
        "email": email,
        "rateLimit": rate_limit,
        "windows": windows,
        "codeReviewRateLimit": code_review,
        "additionalRateLimits": additional_limits,
        "credits": credits,
        "spendControl": spend_control,
        "rateLimitReachedType": rate_limit_reached_type,
    }
