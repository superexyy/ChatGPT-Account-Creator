from __future__ import annotations
import json, random, time, uuid
from ..http_client import CookieJar, fetch_cookie, fetch_redirect
from ..config import AUTHORIZE_DEBUG_FILE, RESEND_DEBUG_FILE
from ..debug_log import append_jsonl, response_snapshot

TOTAL_STEPS = 7
OTP_WAIT_TIMEOUT_MS = 30_000


def response_preview(response, limit: int = 200) -> str:
    try:
        body = response.text or ""
    except Exception:
        body = ""
    body = body.replace("\r", " ").replace("\n", " ").strip()
    if len(body) > limit:
        body = body[: limit - 3] + "..."
    content_type = response.headers.get("content-type", "unknown")
    return f"status={response.status_code} content_type={content_type} body={body or 'empty'}"


def safe_json(response, label: str, progress, allow_empty: bool = False):
    text = ""
    try:
        text = response.text or ""
    except Exception:
        text = ""
    progress(f"{label}: {response_preview(response)}")

    try:
        return response.json()
    except Exception as err:
        if allow_empty and not text.strip():
            progress(f"{label}: empty body treated as empty json")
            return {}
        raise RuntimeError(f"{label} returned non-JSON response: {err}; preview={response_preview(response)}")


def _append_resend_debug(email: str, attempt: int, response) -> None:
    append_jsonl(RESEND_DEBUG_FILE, {"email": email, "attempt": attempt, **response_snapshot(response)})


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


def _format_validate_error(validate_data):
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


def register_account(account, ask_otp_fn, on_progress=None):
    email, full_name = account["email"], account["fullName"]
    progress = on_progress or (lambda *_: None)
    jar = CookieJar(); device_id = str(uuid.uuid4()); session_log_id = str(uuid.uuid4())
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
    progress(1, "Loading auth providers")
    fetch_cookie(jar, "https://chatgpt.com/api/auth/providers", {"headers": login_headers})
    progress(1, "Fetching CSRF token")
    progress(1, "Sending GET /api/auth/csrf")
    csrf_url = "https://chatgpt.com/api/auth/csrf"
    csrf_res = fetch_cookie(jar, csrf_url, {"headers": browser_headers})
    if csrf_res.status_code == 403:
        progress(1, "CSRF request blocked on chatgpt.com, retrying auth.openai.com")
        csrf_url = "https://auth.openai.com/api/auth/csrf"
        csrf_res = fetch_cookie(jar, csrf_url, {"headers": {**browser_headers, "Referer": "https://auth.openai.com/"}})
    csrf_data = safe_json(csrf_res, "CSRF response", progress)
    csrf_token = csrf_data.get("csrfToken")
    if not csrf_token: raise RuntimeError("Failed to obtain CSRF token")
    progress(1, f"CSRF token acquired length={len(csrf_token)}")
    progress(2, "Initiating OAuth signin")
    progress(2, f"Preparing signin for {email}")
    from urllib.parse import urlencode
    signin_params = urlencode({"prompt":"login","ext-oai-did":device_id,"auth_session_logging_id":session_log_id,"ext-passkey-client-capabilities":"00001","screen_hint":"login_or_signup","login_hint":email})
    progress(2, "Sending signin POST")
    signin_res = fetch_cookie(jar, f"https://chatgpt.com/api/auth/signin/openai?{signin_params}", {"method":"POST","headers":{"Content-Type":"application/x-www-form-urlencoded","Accept":"*/*","Origin":"https://chatgpt.com","Referer":login_referer},"data":urlencode({"callbackUrl":"https://chatgpt.com/login","csrfToken":csrf_token,"json":"true"})})
    signin_data = safe_json(signin_res, "Signin response", progress)
    authorize_url = signin_data.get("url")
    if not authorize_url: raise RuntimeError("Failed to obtain OAuth URL")
    progress(2, f"OAuth URL obtained length={len(authorize_url)}")
    progress(3, "Opening registration and triggering OTP")
    progress(3, "Following authorize redirect chain")
    otp_sent_at = time.time() * 1000 - 5000
    otp_page, final_url = fetch_redirect(jar, authorize_url, {"headers": auth_headers})
    _append_authorize_debug(email, "register", otp_page, final_url)
    progress(3, f"Authorize chain ended at {final_url}")
    _ = otp_page.text
    progress(4, "Registration page loaded and OTP request should be in flight")
    progress(4, f"OTP timestamp set to {int(otp_sent_at)}")
    otp_codes = None
    for attempt in range(3):
        attempt_start = time.time()
        if attempt > 0:
            otp_sent_at = time.time() * 1000 - 5000
            progress(5, f"Resending OTP attempt {attempt} of 2")
            progress(5, "Sending resend OTP POST")
            resend_res = fetch_cookie(jar, "https://auth.openai.com/api/accounts/email-otp/resend", {"method":"POST","headers":{"Accept":"*/*","Origin":"https://auth.openai.com","Referer":"https://auth.openai.com/email-verification"}})
            progress(5, f"Resend response status {resend_res.status_code}")
            _append_resend_debug(email, attempt, resend_res)
            time.sleep(2)
        progress(5, f"Waiting for OTP code attempt {attempt + 1} of 3")
        progress(5, f"OTP lookup window starts at {int(otp_sent_at)}")
        try:
            progress(5, f"OTP attempt {attempt + 1} start")
            result = ask_otp_fn(email, after=otp_sent_at, timeout=OTP_WAIT_TIMEOUT_MS, on_progress=progress)
            progress(5, f"OTP attempt {attempt + 1} finished in {time.time() - attempt_start:.1f}s")
            otp_codes = result if isinstance(result, list) else [result]
            if otp_codes:
                break
        except Exception as err:
            progress(5, f"OTP attempt {attempt + 1} failed after {time.time() - attempt_start:.1f}s: {err}")
            if attempt < 2:
                progress(5, "Pausing 1s before next OTP attempt")
                time.sleep(1)
            if attempt == 2: raise RuntimeError("OTP not received after 2 resends")
    progress(5, f"OTP received count={len(otp_codes)} values={', '.join(otp_codes)}")
    val_data = None
    for code in otp_codes:
        progress(6, f"Validating OTP code {code}")
        validate_res = fetch_cookie(jar, "https://auth.openai.com/api/accounts/email-otp/validate", {"method":"POST","headers":{"Content-Type":"application/json","Accept":"application/json","Origin":"https://auth.openai.com","Referer":"https://auth.openai.com/email-verification"},"data":json.dumps({"code": code.strip()})})
        val_data = safe_json(validate_res, "OTP validate response", progress)
        if val_data.get("continue_url"): progress(6, f"OTP validated using code {code}"); break
        progress(6, f"Code {code} rejected")
    if not val_data or not val_data.get("continue_url"): raise RuntimeError(f"OTP validation failed: {_format_validate_error(val_data)}")
    progress(6, "Following continue URL after OTP validation")
    about_page, continue_url = fetch_redirect(jar, val_data["continue_url"], {"headers": {**auth_headers, "Referer": "https://auth.openai.com/email-verification"}})
    progress(6, f"Continue chain ended at {continue_url}")
    _ = about_page.text
    progress(7, "Creating account profile")
    birthdate = f"{2000 + random.randint(0, 5)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
    progress(7, f"Generated birthdate {birthdate}")
    create_res = fetch_cookie(jar, "https://auth.openai.com/api/accounts/create_account", {"method":"POST","headers":{"Content-Type":"application/json","Accept":"application/json","Origin":"https://auth.openai.com","Referer":"https://auth.openai.com/about-you"},"data":json.dumps({"name": full_name, "birthdate": birthdate})})
    create_data = safe_json(create_res, "Create account response", progress)
    if not create_data.get("continue_url"): raise RuntimeError(f"Account creation failed: {json.dumps(create_data)}")
    callback_url = create_data.get("page", {}).get("payload", {}).get("url") or create_data["continue_url"]
    progress(7, f"Callback URL selected {callback_url}")
    cb_res, callback_final_url = fetch_redirect(jar, callback_url, {"headers": {**auth_headers, "Referer": "https://auth.openai.com/"}})
    progress(7, f"Callback chain ended at {callback_final_url}")
    _ = cb_res.text
    session_data = {}
    try:
        progress(7, "Fetching session data")
        session_res = fetch_cookie(jar, "https://chatgpt.com/api/auth/session", {"headers": {"Accept": "application/json", "Referer": "https://chatgpt.com/"}})
        session = safe_json(session_res, "Session response", progress, allow_empty=True)
        if session.get("accessToken"):
            session_data = {"userId": session.get("user", {}).get("id"), "accessToken": session.get("accessToken"), "expires": session.get("expires")}
            progress(7, f"Session token received userId={session_data.get('userId')}")
    except Exception: pass
    progress(7, "Registration flow complete")
    return {**account, **session_data}
