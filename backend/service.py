from __future__ import annotations

import json
import time
from typing import Any, Callable, Dict, List, Optional

from .account_creation.email_gen import create_account_generator
from .account_creation.otp import create_otp_waiter
from .account_creation.register import register_account
from .config import ACCOUNTS_FILE, EMAIL_DB_FILE, EMAIL_DOMAINS, OTP_POLL, OTP_TIMEOUT
from .storage import ensure_data_dir, is_email_used, load_accounts, save_account, save_email_to_db, load_email_db

ProgressLog = Callable[[str], None]


def _emit(log: Optional[ProgressLog], message: str) -> None:
    if log:
        log(message)


def _account_label(account_number: int, email: str = "") -> str:
    return f"Account {account_number} {email}".strip()


def _format_duration(ms: int) -> str:
    if ms >= 60000:
        return f"{ms // 60000}m {(ms // 1000) % 60}s"
    return f"{ms // 1000}s"


def _make_progress_logger(log: Optional[ProgressLog], account_number: int, email: str):
    label = _account_label(account_number, email)

    def progress(*args):
        if len(args) == 1:
            _emit(log, f"{label}: {args[0]}")
        elif len(args) >= 2:
            step, message = args[0], args[1]
            _emit(log, f"{label} step {step}: {message}")

    return progress


def _make_otp_logger(log: Optional[ProgressLog], account_number: int, email: str):
    label = _account_label(account_number, email)

    def progress(*args, **kwargs):
        if args:
            _emit(log, f"{label} OTP: {args[0]}")
        elif "message" in kwargs:
            _emit(log, f"{label} OTP: {kwargs['message']}")

    return progress


def _make_otp_waiter(wait_for_otp, log: Optional[ProgressLog], account_number: int, email: str):
    otp_logger = _make_otp_logger(log, account_number, email)

    def ask_otp(email, after=None, timeout=None, on_progress=None):
        return wait_for_otp(email, after=after, timeout=timeout, on_progress=otp_logger)

    return ask_otp


def _export_accounts_file(accounts: List[Dict[str, Any]]) -> None:
    ACCOUNTS_FILE.write_text(json.dumps(accounts, indent=2), encoding="utf-8")


def _export_email_db_file(emails: List[str]) -> None:
    EMAIL_DB_FILE.write_text(json.dumps(emails, indent=2), encoding="utf-8")


def _is_created_account(result: Dict[str, Any]) -> bool:
    return bool(result.get("accessToken") and result.get("userId") and result.get("email"))


def create_accounts(
    count: int,
    suffix: str = "",
    log: Optional[ProgressLog] = None,
    reset_result: bool = True,
) -> Dict[str, Any]:
    ensure_data_dir()
    generator = create_account_generator({"domains": EMAIL_DOMAINS})
    wait_for_otp = create_otp_waiter({"timeout": OTP_TIMEOUT, "pollInterval": OTP_POLL})

    results: List[Dict[str, Any]] = []
    success = 0
    start = time.time()

    for index in range(count):
        account = generator()
        if suffix:
            local, domain = account["email"].split("@", 1)
            account["email"] = f"{local}{suffix}@{domain}"

        if is_email_used(account["email"]):
            _emit(log, f"{_account_label(index + 1, account['email'])}: email already used, skipping")
            continue

        _emit(log, f"{_account_label(index + 1, account['email'])}: preparing")
        ask_otp_fn = _make_otp_waiter(wait_for_otp, log, index + 1, account["email"])

        try:
            result = register_account(
                account,
                ask_otp_fn,
                on_progress=_make_progress_logger(log, index + 1, account["email"]),
            )
            if not _is_created_account(result):
                _emit(log, f"{_account_label(index + 1, account['email'])}: registration did not return a completed account, skipping save")
                continue
            _emit(log, f"{_account_label(index + 1, account['email'])}: saving result")
            save_account(result)
            save_email_to_db(account["email"])
            results.append(result)
            success += 1
            _emit(log, f"{_account_label(index + 1, account['email'])}: completed")
        except Exception as err:
            _emit(log, f"{_account_label(index + 1, account['email'])}: failed {err}")
            raise

    duration = _format_duration(int((time.time() - start) * 1000))
    return {
        "requested": count,
        "success": success,
        "failed": count - success,
        "duration": duration,
        "results": results,
    }


def export_accounts(kind: str = "both", log: Optional[ProgressLog] = None) -> Dict[str, Any]:
    ensure_data_dir()
    accounts = load_accounts()
    if not accounts:
        _emit(log, "No accounts found in data/accounts.json")
        return {"count": 0, "exported": False}

    emails = load_email_db()
    if kind in ("accounts", "both"):
        _export_accounts_file(accounts)
        _emit(log, f"Exported {len(accounts)} accounts to {ACCOUNTS_FILE.resolve()}")
    if kind in ("email_db", "both"):
        _export_email_db_file(emails)
        _emit(log, f"Exported {len(emails)} emails to {EMAIL_DB_FILE.resolve()}")
    return {
        "count": len(accounts),
        "exported": True,
        "paths": [
            *( [str(ACCOUNTS_FILE.resolve())] if kind in ("accounts", "both") else [] ),
            *( [str(EMAIL_DB_FILE.resolve())] if kind in ("email_db", "both") else [] ),
        ],
    }
