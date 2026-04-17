from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from flask import Flask, jsonify, redirect, render_template, request, url_for

from backend.config import MAILCOW_IMAP, OTP_POLL, OTP_TIMEOUT, TOTAL_STEPS
from backend import jobs
from backend.service import create_accounts, export_accounts
from backend.account_verification import verify_account_by_email
from backend.account_creation.otp import create_otp_waiter
from backend.storage import delete_account, load_accounts, update_account_fields
from .i18n import build_i18n, get_locale, translate


TEMPLATE_DIR = Path(__file__).resolve().parent / "webui"
KST = timezone(timedelta(hours=9), "KST")


def _safe_account_return_target(email: str, candidate: str | None) -> str:
    default_target = url_for("account_detail", email=email)
    if not candidate:
        return default_target

    target = str(candidate).strip()
    if not target.startswith("/"):
        return default_target
    if target.startswith("/accounts"):
        return target
    return default_target


def _format_datetime(value: Any) -> str:
    if not value:
        return "-"
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M:%S KST")


def _job_progress_summary(job: Dict[str, Any]) -> Dict[str, Any]:
    logs = job.get("logs") or []
    total = None
    if isinstance(job.get("params"), dict):
        total = job["params"].get("count")
    result = job.get("result") or {}
    result_success = result.get("success")

    if job.get("type") == "verify":
        latest_message = ""
        if logs:
            latest_message = str(logs[-1].get("message") or "")

        current_email = ""
        if isinstance(job.get("params"), dict):
            current_email = str(job["params"].get("email") or "")

        stage_line = "검증 작업을 준비하는 중입니다."
        status_text = "검증 작업이 대기 중입니다."
        progress_percent = 0

        lower_latest = latest_message.lower()
        if "logging in via email" in lower_latest:
            stage_line = "이메일 로그인 절차를 시작했습니다."
            status_text = "인증 경로를 준비하는 중입니다."
            progress_percent = 15
        elif "authorize chain ended" in lower_latest:
            stage_line = "인증 화면으로 이동했습니다."
            status_text = "OTP를 기다리는 중입니다."
            progress_percent = 35
        elif "waiting for otp code" in lower_latest or "otp wait" in lower_latest:
            stage_line = "OTP 메일을 기다리는 중입니다."
            status_text = "메일을 확인하는 중입니다."
            progress_percent = 50
        elif "validating otp code" in lower_latest:
            stage_line = "OTP를 검증하는 중입니다."
            status_text = "OTP를 확인하는 중입니다."
            progress_percent = 65
        elif "fetching session data" in lower_latest or "session" in lower_latest:
            stage_line = "세션과 quota 정보를 확인하는 중입니다."
            status_text = "계정 생존 여부를 확인하는 중입니다."
            progress_percent = 85
        elif "completed" in lower_latest:
            stage_line = "검증이 완료되었습니다."
            status_text = "검증 작업이 완료되었습니다."
            progress_percent = 100
        elif "failed" in lower_latest:
            stage_line = "검증에 실패했습니다."
            status_text = "검증 작업이 실패했습니다."
            progress_percent = 100

        if job.get("status") == "running":
            progress_percent = max(progress_percent, 5)
        elif job.get("status") == "completed":
            progress_percent = 100
        elif job.get("status") == "failed":
            progress_percent = 100

        return {
            "account_line": f"{current_email or '검증 대상'} 계정을 처리 중입니다.",
            "current_email": current_email,
            "step_line": stage_line,
            "status_text": status_text,
            "progress_percent": progress_percent,
            "current_step": 0,
        }

    current_account = None
    current_email = ""
    current_step = None
    step_label = ""
    status_text = ""

    step_labels = {
        1: "로그인 토큰을 확인하는 단계입니다.",
        2: "인증 경로를 준비하는 단계입니다.",
        3: "등록 페이지를 열고 OTP 발송을 시작하는 단계입니다.",
        4: "등록 페이지가 열렸는지 확인하는 단계입니다.",
        5: "OTP 메일을 기다리고 다시 요청할 수 있는 단계입니다.",
        6: "OTP 코드를 검증하는 단계입니다.",
        7: "계정 정보를 제출하고 최종 등록을 완료하는 단계입니다.",
    }

    for entry in reversed(logs):
        message = str(entry.get("message") or "")
        if "Account " in message:
            if current_account is None:
                import re

                match = re.search(r"Account\s+(\d+)", message)
                if match:
                    current_account = int(match.group(1))
            if not current_email:
                import re

                email_match = re.search(r"Account\s+\d+\s+(?P<email>[^:\s]+@[^:\s]+)", message)
                if email_match:
                    current_email = email_match.group("email")
            if current_step is None:
                import re

                step_match = re.search(r"step\s+(\d+)", message, re.IGNORECASE)
                if step_match:
                    current_step = int(step_match.group(1))
                    step_label = step_labels.get(current_step, "")

            if "preparing" in message:
                status_text = "계정 생성을 준비하는 중입니다."
            elif "CSRF token" in message:
                status_text = "로그인용 토큰을 확인하는 중입니다."
            elif "OAuth URL obtained" in message:
                status_text = "인증 경로를 준비하는 중입니다."
            elif "authorize redirect chain" in message.lower():
                status_text = "등록 화면으로 이동하는 중입니다."
            elif "registration page loaded" in message.lower():
                status_text = "등록 화면을 열었고 OTP를 기다리는 중입니다."
            elif "OTP" in message and "waiting" in message.lower():
                status_text = "OTP 메일을 기다리는 중입니다."
            elif "OTP" in message and ("validated" in message or "received" in message):
                status_text = "OTP를 확인하는 중입니다."
            elif "resending otp" in message.lower():
                status_text = "OTP를 다시 요청하는 중입니다."
            elif "otp attempt" in message.lower() and "failed" in message.lower():
                status_text = "OTP 확인에 실패해서 다시 시도하는 중입니다."
            elif "validating otp code" in message.lower():
                status_text = "받은 OTP를 검증하는 중입니다."
            elif "continue url after otp validation" in message.lower():
                status_text = "OTP 검증 후 다음 단계로 이동하는 중입니다."
            elif "creating account profile" in message.lower():
                status_text = "계정 정보를 마지막으로 작성하는 중입니다."
            elif "generated birthdate" in message.lower():
                status_text = "생년월일을 생성해서 등록 정보에 넣는 중입니다."
            elif "callback url selected" in message.lower():
                status_text = "마지막 등록 주소를 확인하는 중입니다."
            elif "fetching session data" in message.lower():
                status_text = "세션 정보를 확인하는 중입니다."
            elif "completed" in message:
                status_text = "계정 생성이 완료되었습니다."
            elif "failed" in message:
                status_text = "계정 생성에 실패했습니다."

        if current_account is not None and current_step is not None and status_text:
            break

    if total and current_account:
        account_line = f"{total}개 중 {current_account}번째 계정을 처리 중입니다."
    elif total:
        account_line = f"총 {total}개 계정을 처리 중입니다."
    else:
        account_line = "진행 정보를 확인하는 중입니다."

    if isinstance(total, int) and total > 0:
        if job.get("status") == "completed" and isinstance(result_success, int):
            progress_percent = 100
        elif current_account:
            account_base = (current_account - 1) / total
            step_ratio = 0.0
            if current_step and TOTAL_STEPS:
                step_ratio = min(max(current_step, 0), TOTAL_STEPS) / (TOTAL_STEPS + 1)
            progress_percent = max(0, min(99, int((account_base + (step_ratio / total)) * 100)))
        elif job.get("status") == "failed" and isinstance(result_success, int):
            progress_percent = max(0, min(99, int(result_success / total * 100)))
        else:
            progress_percent = 0
    else:
        progress_percent = 0

    if current_step:
        if step_label:
            step_line = f"현재 {current_step}단계 진행 중입니다. {step_label}"
        else:
            step_line = f"현재 {current_step}단계 진행 중입니다."
    else:
        step_line = "현재 단계 정보를 확인하는 중입니다."

    if not status_text:
        if job.get("status") == "running":
            status_text = "작업이 진행 중입니다."
        elif job.get("status") == "completed":
            status_text = "작업이 완료되었습니다."
        elif job.get("status") == "failed":
            status_text = "작업이 실패했습니다."
        else:
            status_text = "작업 상태를 확인하는 중입니다."

    return {
        "account_line": account_line,
        "current_email": current_email,
        "step_line": step_line,
        "status_text": status_text,
        "progress_percent": progress_percent,
        "current_step": current_step or 0,
    }


def _run_create_job(job_id: str, count: int, suffix: str) -> None:
    jobs.update_job(job_id, status="running", startedAt=jobs.now_iso())
    logger = jobs.make_job_logger(job_id, echo=True)
    try:
        result = create_accounts(count=count, suffix=suffix, log=logger)
        jobs.update_job(job_id, status="completed", finishedAt=jobs.now_iso(), result=result)
    except Exception as err:
        jobs.update_job(job_id, status="failed", finishedAt=jobs.now_iso(), error=str(err))


def _run_verify_job(job_id: str, email: str, return_target: str) -> None:
    jobs.update_job(job_id, status="running", startedAt=jobs.now_iso())
    logger = jobs.make_job_logger(job_id, echo=True)
    wait_for_otp = create_otp_waiter(
        {
            "timeout": OTP_TIMEOUT,
            "pollInterval": OTP_POLL,
            "imapHost": MAILCOW_IMAP.get("host"),
            "imapPort": MAILCOW_IMAP.get("port"),
            "imapSsl": MAILCOW_IMAP.get("ssl"),
            "imapUsername": MAILCOW_IMAP.get("username"),
            "imapPassword": MAILCOW_IMAP.get("password"),
            "mailbox": MAILCOW_IMAP.get("mailbox"),
            "scanLimit": MAILCOW_IMAP.get("scan_limit"),
            "logLimit": MAILCOW_IMAP.get("log_limit"),
        }
    )

    try:
        progress = verify_account_by_email(email, wait_for_otp, on_progress=logger)
        alive = bool(progress.get("alive"))
        update_account_fields(
            email,
            {
                "codex": alive,
                "alive": alive,
                "accessToken": progress.get("accessToken") or "",
                "userId": progress.get("userId") or "",
                "accountId": progress.get("accountId") or progress.get("userId") or "",
                "expires": progress.get("expires") or "",
                "quotaSummary": progress.get("quotaSummary"),
                "quotaError": progress.get("quotaError") or "",
                "lastVerifiedAt": jobs.now_iso(),
                "verification": {
                    "loggedIn": bool(progress.get("loggedIn")),
                    "alive": alive,
                    "codexAlive": bool(progress.get("codexAlive")),
                    "userId": progress.get("userId") or "",
                    "accountId": progress.get("accountId") or "",
                    "hasQuota": bool(progress.get("quotaSummary")),
                    "quotaError": progress.get("quotaError") or "",
                    "status": "ok" if alive else "partial",
                },
            },
        )
        jobs.update_job(
            job_id,
            status="completed",
            finishedAt=jobs.now_iso(),
            result={"email": email, "alive": alive, "codexAlive": bool(progress.get("codexAlive")), "returnTarget": return_target},
        )
    except Exception as err:
        update_account_fields(
            email,
            {
                "codex": False,
                "alive": False,
                "lastVerifiedAt": jobs.now_iso(),
                "verification": {
                    "loggedIn": False,
                    "alive": False,
                    "status": "error",
                    "error": str(err),
                },
            },
        )
        jobs.update_job(job_id, status="failed", finishedAt=jobs.now_iso(), error=str(err), result={"email": email, "returnTarget": return_target})


def _run_export_job(job_id: str) -> None:
    jobs.update_job(job_id, status="running", startedAt=jobs.now_iso())
    logger = jobs.make_job_logger(job_id, echo=True)
    try:
        export_kind = jobs.get_job(job_id).get("params", {}).get("kind", "both")
        result = export_accounts(kind=export_kind, log=logger)
        jobs.update_job(job_id, status="completed", finishedAt=jobs.now_iso(), result=result)
    except Exception as err:
        jobs.update_job(job_id, status="failed", finishedAt=jobs.now_iso(), error=str(err))


def _start_thread(target, *args):
    thread = threading.Thread(target=target, args=args, daemon=True)
    thread.start()


def _parse_positive_int(raw_value: str, default: int = 1) -> int:
    try:
        return max(1, int(raw_value or str(default)))
    except ValueError:
        return default


def create_app() -> Flask:
    app = Flask(__name__, template_folder=str(TEMPLATE_DIR), static_folder=str(TEMPLATE_DIR / "static"), static_url_path="/static")
    app.jinja_env.filters["human_datetime"] = _format_datetime
    app.jinja_env.globals["t"] = lambda key, locale=None, default="": translate(locale or get_locale(), key, default)

    @app.get("/")
    def index():
        locale = get_locale(request.args)
        return render_template("index.html", jobs=jobs.list_jobs(), i18n=build_i18n(locale))

    @app.get("/accounts")
    def account_list():
        locale = get_locale(request.args)
        return render_template("accounts.html", accounts=load_accounts(), i18n=build_i18n(locale))

    @app.get("/accounts/<path:email>")
    def account_detail(email: str):
        locale = get_locale(request.args)
        account = next((item for item in load_accounts() if (item.get("email") or "") == email), None)
        if not account:
            return redirect(url_for("account_list"))
        return render_template("account_detail.html", account=account, i18n=build_i18n(locale))

    @app.post("/backend/accounts/<path:email>/verify")
    def verify_account(email: str):
        account = next((item for item in load_accounts() if (item.get("email") or "") == email), None)
        if not account:
            return redirect(url_for("account_list"))

        return_target = _safe_account_return_target(email, request.form.get("next") or request.args.get("next"))
        job = jobs.create_job("verify", {"email": email, "returnTarget": return_target})
        _start_thread(_run_verify_job, job["id"], email, return_target)

        payload = {
            "jobId": job["id"],
            "jobUrl": url_for("job_detail", job_id=job["id"]),
            "accountUrl": return_target,
        }
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in (request.headers.get("Accept") or ""):
            return jsonify(payload), 202
        return redirect(return_target)

    @app.post("/backend/accounts/<path:email>/delete")
    def delete_account_route(email: str):
        if delete_account(email):
            return redirect(url_for("account_list"))
        return redirect(url_for("account_list"))

    @app.post("/backend/jobs/create")
    def start_create():
        count = _parse_positive_int(request.form.get("count") or "1")
        suffix = (request.form.get("suffix") or "").strip()
        job = jobs.create_job("create", {"count": count, "suffix": suffix})
        _start_thread(_run_create_job, job["id"], count, suffix)
        return redirect(url_for("job_detail", job_id=job["id"]))

    @app.post("/backend/jobs/export")
    def start_export():
        export_kind = (request.form.get("kind") or "both").strip()
        if export_kind not in {"accounts", "email_db", "both"}:
            export_kind = "both"
        job = jobs.create_job("export", {"kind": export_kind})
        _start_thread(_run_export_job, job["id"])
        return redirect(url_for("job_detail", job_id=job["id"]))

    @app.get("/backend/jobs/<job_id>")
    def job_detail(job_id: str):
        locale = get_locale(request.args)
        job = jobs.get_job(job_id)
        if not job:
            job = {"id": job_id, "type": "unknown", "status": "deleted", "createdAt": "", "updatedAt": "", "error": "", "logs": [], "result": None, "params": {}}
        return render_template("job.html", job=job, progress=_job_progress_summary(job), i18n=build_i18n(locale))

    @app.post("/backend/jobs/<job_id>/delete")
    def delete_job(job_id: str):
        jobs.delete_job(job_id)
        return redirect(url_for("index"))

    @app.get("/backend/jobs")
    def api_jobs():
        locale = get_locale(request.args)
        return jsonify({"jobs": jobs.list_jobs(), "i18n": build_i18n(locale)})

    @app.get("/backend/jobs/<job_id>/data")
    def api_job(job_id: str):
        locale = get_locale(request.args)
        job = jobs.get_job(job_id)
        if not job:
            return jsonify({"error": "not found"}), 404
        return jsonify({"job": job, "progress": _job_progress_summary(job), "i18n": build_i18n(locale)})

    @app.get("/backend/accounts")
    def api_accounts():
        locale = get_locale(request.args)
        return jsonify({"accounts": load_accounts(), "i18n": build_i18n(locale)})

    @app.post("/backend/accounts/<path:email>/codex")
    def mark_codex_by_email(email: str):
        normalized = (email or "").strip()
        if normalized:
            update_account_flag(normalized, "codex", True)
        return redirect(url_for("account_list"))

    return app


def run(host: str = "127.0.0.1", port: int = 5000) -> None:
    app = create_app()
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
