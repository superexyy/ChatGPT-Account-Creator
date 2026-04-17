from __future__ import annotations

import json
import random
import time
import uuid
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlencode

from .config import AUTHORIZE_DEBUG_FILE, CHATGPT_QUOTA_URL
from .debug_log import append_jsonl, response_snapshot
from .quota import parse_quota_usage
from .http_client import CookieJar, fetch_cookie, fetch_redirect

ProgressLog = Callable[[str], None]


def _emit(log: Optional[ProgressLog], message: str) -> None:
    if log:
        log(message)


def _safe_json(response, label: str, progress):
    try:
        return response.json()
    except Exception as err:
        raise RuntimeError(f"{label} returned non-JSON response: {err}; status={response.status_code}")


def _append_authorize_debug(email: str, stage: str, response, final_url: str) -> None:
    append_jsonl(
        AUTHORIZE_DEBUG_FILE,
        {
            "email": email,
            "stage": stage,
            "finalUrl": final_url,
            **response_snapshot(response),
        },
    )


def _format_validate_error(validate_data: Any) -> str:
    if isinstance(validate_data, dict):
        error = validate_data.get("error")
        if isinstance(error, dict):
            code = str(error.get("code") or "").strip()
            message = str(error.get("message") or "").strip()
            parts = [part for part in [code, message] if part]
            if parts:
                return " / ".join(parts)
        if error:
            return str(error)
        if validate_data:
            return json.dumps(validate_data, ensure_ascii=False)
    if validate_data is None:
        return "empty validate response"
    return str(validate_data)


def _login_via_email_otp(email: str, ask_otp_fn, on_progress=None) -> Dict[str, Any]:
    progress = on_progress or (lambda *_: None)
    jar = CookieJar()
    device_id = str(uuid.uuid4())
    session_log_id = str(uuid.uuid4())
    login_referer = "https://chatgpt.com/login"

    browser_headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": login_referer,
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "X-Requested-With": "XMLHttpRequest",
    }
    login_headers = {"Accept": "*/*", "Content-Type": "application/json", "Referer": login_referer}
    auth_headers = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Referer": "https://chatgpt.com/"}

    progress(f"Logging in via email for {email}")
    fetch_cookie(jar, "https://chatgpt.com/api/auth/providers", {"headers": login_headers})
    csrf_res = fetch_cookie(jar, "https://chatgpt.com/api/auth/csrf", {"headers": browser_headers})
    if csrf_res.status_code == 403:
        csrf_res = fetch_cookie(
            jar,
            "https://auth.openai.com/api/auth/csrf",
            {"headers": {**browser_headers, "Referer": "https://auth.openai.com/"}},
        )
    csrf_data = _safe_json(csrf_res, "CSRF response", progress)
    csrf_token = csrf_data.get("csrfToken")
    if not csrf_token:
        raise RuntimeError("Failed to obtain CSRF token")

    signin_params = urlencode(
        {
            "prompt": "login",
            "ext-oai-did": device_id,
            "auth_session_logging_id": session_log_id,
            "ext-passkey-client-capabilities": "00001",
            "screen_hint": "login_or_signup",
            "login_hint": email,
        }
    )
    signin_res = fetch_cookie(
        jar,
        f"https://chatgpt.com/api/auth/signin/openai?{signin_params}",
        {
            "method": "POST",
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "*/*",
                "Origin": "https://chatgpt.com",
                "Referer": login_referer,
            },
            "data": urlencode({"callbackUrl": "https://chatgpt.com/login", "csrfToken": csrf_token, "json": "true"}),
        },
    )
    signin_data = _safe_json(signin_res, "Signin response", progress)
    authorize_url = signin_data.get("url")
    if not authorize_url:
        raise RuntimeError("Failed to obtain OAuth URL")

    otp_sent_at = time.time() * 1000 - 5000
    authorize_res, final_url = fetch_redirect(jar, authorize_url, {"headers": auth_headers})
    _append_authorize_debug(email, "verify", authorize_res, final_url)
    progress(f"Authorize chain ended at {final_url}")

    otp_codes = ask_otp_fn(email, after=otp_sent_at)
    if not isinstance(otp_codes, list):
        otp_codes = [otp_codes]
    otp_codes = [str(code).strip() for code in otp_codes if str(code).strip()]
    if not otp_codes:
        raise RuntimeError("OTP not received")

    validate_data = None
    for code in otp_codes:
        progress("Validating OTP code")
        validate_res = fetch_cookie(
            jar,
            "https://auth.openai.com/api/accounts/email-otp/validate",
            {
                "method": "POST",
                "headers": {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Origin": "https://auth.openai.com",
                    "Referer": "https://auth.openai.com/email-verification",
                },
                "data": json.dumps({"code": code}),
            },
        )
        _append_authorize_debug(email, "validate", validate_res, "https://auth.openai.com/api/accounts/email-otp/validate")
        validate_data = _safe_json(validate_res, "OTP validate response", progress)
        if validate_data.get("continue_url"):
            break
    if not validate_data or not validate_data.get("continue_url"):
        raise RuntimeError(f"OTP validation failed: {_format_validate_error(validate_data)}")

    continue_res, continue_final_url = fetch_redirect(
        jar,
        validate_data["continue_url"],
        {"headers": {**auth_headers, "Referer": "https://auth.openai.com/email-verification"}},
    )
    _append_authorize_debug(email, "continue", continue_res, continue_final_url)

    session_res = fetch_cookie(jar, "https://chatgpt.com/api/auth/session", {"headers": {"Accept": "application/json", "Referer": "https://chatgpt.com/"}})
    _append_authorize_debug(email, "session", session_res, "https://chatgpt.com/api/auth/session")
    session = _safe_json(session_res, "Session response", progress)
    access_token = session.get("accessToken") or ""
    session_user_id = session.get("user", {}).get("id") or session.get("userId") or session.get("accountId") or ""
    result: Dict[str, Any] = {
        "email": email,
        "loggedIn": bool(access_token),
        "alive": False,
        "codexAlive": False,
        "userId": session_user_id,
        "accountId": session.get("accountId") or session_user_id,
        "accessToken": access_token,
        "expires": session.get("expires") or "",
        "session": session,
    }

    if CHATGPT_QUOTA_URL and access_token:
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        if session_user_id:
            headers["ChatGPT-Account-Id"] = str(session_user_id)
        quota_res = fetch_cookie(jar, CHATGPT_QUOTA_URL, {"headers": headers})
        _append_authorize_debug(email, "quota", quota_res, CHATGPT_QUOTA_URL)
        if quota_res.ok:
            try:
                quota_raw = quota_res.json()
            except Exception as err:
                result["quotaError"] = f"quota response was not JSON: {err}"
            else:
                quota = parse_quota_usage(quota_raw)
                result["quotaSummary"] = {
                    "alive": bool(quota["alive"]),
                    "planType": quota["planType"],
                    "userId": quota["userId"],
                    "accountId": quota["accountId"],
                    "email": quota["email"],
                    "rateLimit": quota["rateLimit"],
                    "windows": quota["windows"],
                    "codeReviewRateLimit": quota["codeReviewRateLimit"],
                    "additionalRateLimits": quota["additionalRateLimits"],
                    "credits": quota["credits"],
                    "spendControl": quota["spendControl"],
                    "rateLimitReachedType": quota["rateLimitReachedType"],
                }
                result["userId"] = quota["userId"] or result["userId"]
                result["accountId"] = quota["accountId"] or result["accountId"]
                result["email"] = quota["email"] or result["email"]
                result["alive"] = bool(quota["alive"])
                result["codexAlive"] = bool(quota["alive"])
                if not quota["alive"]:
                    result["quotaError"] = "quota response missing account identity fields"
        else:
            result["quotaError"] = f"quota request failed: {quota_res.status_code} {quota_res.reason}"
    else:
        missing_parts = []
        if not access_token:
            missing_parts.append("accessToken missing")
        if not CHATGPT_QUOTA_URL:
            missing_parts.append("quota url missing")
        result["quotaError"] = "quota check skipped because " + ", ".join(missing_parts or ["unknown reason"])

    return result


def verify_account_by_email(email: str, ask_otp_fn, on_progress=None) -> Dict[str, Any]:
    progress = on_progress or (lambda *_: None)
    progress(f"Email login verification started for {email}")
    result = _login_via_email_otp(email, ask_otp_fn, on_progress=progress)
    progress(f"Email login verification completed for {email}")
    return result
