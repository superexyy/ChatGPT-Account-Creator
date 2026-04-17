from __future__ import annotations

import email
import imaplib
import re
import socket
import time
from datetime import datetime, timedelta, timezone
from email import policy
from email.header import decode_header, make_header
from email.message import EmailMessage, Message
from email.parser import BytesParser
from email.utils import getaddresses
from html import unescape
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import AUTHORIZE_DEBUG_FILE, LOG_DIR, MAILCOW_IMAP
from ..debug_log import append_jsonl


EMAIL_RE = r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}"


def strip_html(html: str) -> str:
    html = unescape(html or "")
    html = re.sub(r"<!--[\s\S]*?-->", " ", html)
    html = re.sub(r"<style[^>]*>[\s\S]*?</style>", " ", html, flags=re.I)
    html = re.sub(r"<script[^>]*>[\s\S]*?</script>", " ", html, flags=re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    html = unescape(html)
    return re.sub(r"\s+", " ", html).strip()


def normalize_email_address(value: str) -> str:
    value = value or ""
    value = value.strip().strip("<>").lower()
    return value


def extract_header_addresses(value: str) -> List[str]:
    addresses = []
    for _, address in getaddresses([value or ""]):
        normalized = normalize_email_address(address)
        if normalized:
            addresses.append(normalized)
    if addresses:
        return addresses

    for match in re.finditer(EMAIL_RE, value or "", flags=re.I):
        normalized = normalize_email_address(match.group(0))
        if normalized:
            addresses.append(normalized)
    return addresses


def first_header_address(msg: Message, header_name: str) -> str:
    for value in msg.get_all(header_name, []):
        decoded = _decode_mime(str(value))
        addresses = extract_header_addresses(decoded)
        if addresses:
            return addresses[0]
    return ""


def parse_email_timestamp(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = email.utils.parsedate_tz(value)
        if dt is None:
            return None
        return datetime.fromtimestamp(email.utils.mktime_tz(dt), tz=timezone.utc)
    except Exception:
        return None


def parse_imap_internal_date(value: bytes) -> Optional[datetime]:
    if not value:
        return None
    try:
        raw = value.decode("utf-8", errors="replace") if isinstance(value, (bytes, bytearray)) else str(value)
        match = re.search(r'INTERNALDATE\s+"([^"]+)"', raw, flags=re.I)
        if not match:
            return None
        dt = email.utils.parsedate_tz(match.group(1))
        if dt is None:
            return None
        return datetime.fromtimestamp(email.utils.mktime_tz(dt), tz=timezone.utc)
    except Exception:
        return None


def select_target_recipient(msg: Message) -> str:
    x_original_to = first_header_address(msg, "X-Original-To")
    if x_original_to:
        return x_original_to

    to_address = first_header_address(msg, "To")
    if to_address:
        return to_address

    return first_header_address(msg, "Delivered-To")


def extract_delivery_recipient(msg: Message) -> str:
    return first_header_address(msg, "Delivered-To")


def extract_otp_from_text(text: str) -> Optional[str]:
    if not text:
        return None

    normalized = strip_html(text)
    spaced_code = r"((?:\d\s*){6})"
    precise_patterns = [
        rf"Enter\s+this\s+temporary\s+verification\s+code\s+to\s+continue\s*:.{{0,500}}?(?<!\d){spaced_code}(?!\d)",
        rf"(?:temporary\s+)?verification\s+code.{{0,500}}?(?<!\d){spaced_code}(?!\d)",
    ]

    for pat in precise_patterns:
        match = re.search(pat, normalized, flags=re.I | re.S)
        if match:
            code = re.sub(r"\D", "", match.group(1))
            if len(code) == 6:
                return code
    return None


def extract_otp_from_html(html: str) -> Optional[str]:
    if not html:
        return None

    text = strip_html(html)
    return extract_otp_from_text(text)


def extract_otp(message: Dict[str, Any]) -> Optional[str]:
    text_body = message.get("text_body") or ""
    html_body = message.get("html_body") or ""

    candidates = [text_body, html_body]
    for candidate in candidates:
        if not candidate:
            continue
        otp = extract_otp_from_text(candidate)
        if otp:
            return otp

    otp = extract_otp_from_html(html_body)
    if otp:
        return otp

    return None


def _decode_mime(value: str) -> str:
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _part_body(part: Message) -> str:
    if isinstance(part, EmailMessage):
        try:
            content = part.get_content()
            return content if isinstance(content, str) else str(content)
        except Exception:
            pass

    payload = part.get_payload(decode=True) or b""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except Exception:
        return payload.decode("utf-8", errors="replace")


def _parse_email_message(raw: bytes) -> Dict[str, Any]:
    msg: Message = BytesParser(policy=policy.default).parsebytes(raw)
    raw_source = raw.decode("utf-8", errors="replace")
    subject = _decode_mime(msg.get("Subject", ""))
    from_address = _decode_mime(msg.get("From", ""))
    original_to = select_target_recipient(msg)
    delivered_to = extract_delivery_recipient(msg)
    date_header = msg.get("Date", "")

    text_parts: List[str] = []
    html_parts: List[str] = []

    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            content_type = part.get_content_type()
            body = _part_body(part)
            if content_type == "text/plain":
                text_parts.append(body)
            elif content_type == "text/html":
                html_parts.append(body)
    else:
        body = _part_body(msg)
        content_type = msg.get_content_type()
        if content_type == "text/html":
            html_parts.append(body)
        else:
            text_parts.append(body)

    sent_at = parse_email_timestamp(date_header)

    return {
        "raw_source": raw_source,
        "original_to": original_to,
        "delivered_to": delivered_to,
        "subject": subject,
        "from_address": from_address,
        "text_body": "\n".join(text_parts),
        "html_body": "\n".join(html_parts),
        "sent_at": sent_at.isoformat() if sent_at else "",
        "received_at": sent_at.isoformat() if sent_at else "",
    }


def _store_latest_raw_source(raw_source: str) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    dump_path = LOG_DIR / "latest-imap.eml"
    dump_path.write_text(raw_source, encoding="utf-8")
    return dump_path


def _append_imap_debug(email: str, event: str, **details: Any) -> None:
    append_jsonl(
        AUTHORIZE_DEBUG_FILE,
        {
            "email": email,
            "stage": "otp_wait",
            "event": event,
            **details,
        },
    )


def collect_codes(messages: List[Dict[str, Any]], min_date: datetime) -> List[str]:
    def parsed_dt(item: Dict[str, Any]) -> datetime:
        raw = item.get("received_at") or ""
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return datetime.min.replace(tzinfo=timezone.utc)

    codes: List[str] = []
    for msg in sorted(messages, key=parsed_dt, reverse=True):
        is_from_openai = "openai.com" in (msg.get("from_address") or "")
        is_otp_subject = re.search(r"chatgpt|verification|code", msg.get("subject") or msg.get("text_body") or "", flags=re.I) is not None
        is_fresh = parsed_dt(msg) >= min_date

        if (is_from_openai or is_otp_subject) and is_fresh:
            otp = extract_otp(msg)
            if otp and otp not in codes:
                codes.append(otp)

    return codes


def _fetch_recent_messages(imap: imaplib.IMAP4_SSL, mailbox: str, limit: int = 1) -> List[Dict[str, Any]]:
    status, _ = imap.select(mailbox, readonly=True)
    if status != "OK":
        raise RuntimeError(f"Failed to select mailbox {mailbox}")

    status, data = imap.search(None, "ALL")
    if status != "OK":
        return []

    ids = data[0].split()
    if not ids:
        return []

    recent_ids = ids[-limit:]
    messages: List[Dict[str, Any]] = []
    for msg_id in reversed(recent_ids):
        status, fetched = imap.fetch(msg_id, "(RFC822 INTERNALDATE)")
        if status != "OK" or not fetched:
            continue
        meta = fetched[0][0] if fetched and fetched[0] else b""
        raw = fetched[0][1]
        if raw:
            message = _parse_email_message(raw)
            received_at = parse_imap_internal_date(meta)
            if received_at:
                message["received_at"] = received_at.isoformat()
                message["imap_received_at"] = received_at.isoformat()
            else:
                message["imap_received_at"] = message.get("received_at") or ""
            messages.append(message)
    return messages


def is_recent_message(message: Dict[str, Any], min_date: datetime, tolerance_seconds: int) -> bool:
    sent_raw = message.get("sent_at") or message.get("received_at") or ""
    received_raw = message.get("imap_received_at") or message.get("received_at") or ""

    sent_at = None
    received_at = None

    try:
        sent_at = datetime.fromisoformat(sent_raw.replace("Z", "+00:00")) if sent_raw else None
    except Exception:
        sent_at = None

    try:
        received_at = datetime.fromisoformat(received_raw.replace("Z", "+00:00")) if received_raw else None
    except Exception:
        received_at = None

    if sent_at is None and received_at is None:
        return False

    tolerance = timedelta(seconds=tolerance_seconds)
    lower_bound = min_date - tolerance

    if received_at is not None:
        return received_at >= lower_bound

    candidate = sent_at or received_at
    if candidate is None:
        return False
    return candidate >= lower_bound


def create_otp_waiter(config: Dict[str, Any]):
    timeout = config.get("timeout", 90000)
    poll_interval = config.get("pollInterval", 4000)
    timestamp_tolerance = int(config.get("timestampTolerance") or 120)
    on_progress_default = config.get("onProgress") or (lambda *_: None)

    imap_host = config.get("imapHost") or MAILCOW_IMAP.get("host")
    imap_port = int(config.get("imapPort") or MAILCOW_IMAP.get("port") or 993)
    imap_ssl = bool(config.get("imapSsl") if config.get("imapSsl") is not None else MAILCOW_IMAP.get("ssl", True))
    imap_user = config.get("imapUsername") or MAILCOW_IMAP.get("username")
    imap_pass = config.get("imapPassword") or MAILCOW_IMAP.get("password")
    mailbox = config.get("mailbox") or MAILCOW_IMAP.get("mailbox") or "INBOX"
    connect_timeout = int(config.get("connectTimeout") or 10)
    scan_limit = int(config.get("scanLimit") or MAILCOW_IMAP.get("scan_limit") or 10)
    log_limit = int(config.get("logLimit") or MAILCOW_IMAP.get("log_limit") or 1)
    if scan_limit < 1:
        scan_limit = 1
    if log_limit < 1:
        log_limit = 1

    if not imap_host:
        raise RuntimeError("Missing IMAP host in .env as MAILCOW_IMAP_HOST")
    if imap_port == 993 and not imap_ssl:
        imap_ssl = True

    def connect():
        previous_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(connect_timeout)
        try:
            if imap_ssl:
                client = imaplib.IMAP4_SSL(imap_host, imap_port)
            else:
                client = imaplib.IMAP4(imap_host, imap_port)
            if imap_user and imap_pass:
                status, data = client.login(imap_user, imap_pass)
                if status != "OK":
                    raise RuntimeError(f"IMAP login failed: {data}")
            return client
        finally:
            socket.setdefaulttimeout(previous_timeout)

    def short_text(value: str, limit: int = 60) -> str:
        value = re.sub(r"\s+", " ", value or "").strip()
        if len(value) <= limit:
            return value
        return value[: limit - 3] + "..."

    def body_preview(msg: Dict[str, Any], limit: int = 160) -> str:
        text_body = short_text(msg.get("text_body") or "", limit)
        html_body = short_text(strip_html(msg.get("html_body") or ""), limit)
        if text_body and html_body:
            return f"text={text_body} | html={html_body}"
        if text_body:
            return f"text={text_body}"
        if html_body:
            return f"html={html_body}"
        return "body=empty"

    def describe_message(msg: Dict[str, Any]) -> str:
        subject = short_text(msg.get("subject") or "", 80)
        sender = short_text(msg.get("from_address") or "", 80)
        received_at = msg.get("received_at") or "unknown"
        original_to = msg.get("original_to") or "unknown"
        delivered_to = msg.get("delivered_to") or "unknown"
        return f"subject={subject} from={sender} original_to={original_to} delivered_to={delivered_to} received_at={received_at}"

    def wait_for_otp(email: str, after=None, timeout=None, on_progress=None):
        if not email or "@" not in email:
            raise RuntimeError(f"Invalid email format: {email}")

        progress = on_progress or on_progress_default

        effective_timeout = int(timeout or config.get("timeout") or 90000)
        start = time.time() * 1000
        min_date = datetime.fromtimestamp((after or (start - 30000)) / 1000, tz=timezone.utc)
        progress(f"OTP wait started for {email}")
        progress(f"OTP timeout configured to {effective_timeout}ms")
        progress(f"OTP poll interval configured to {poll_interval}ms")
        progress(f"OTP timestamp tolerance configured to {timestamp_tolerance}s")
        progress(f"OTP IMAP scan limit configured to {scan_limit} recent message(s)")
        progress(f"OTP IMAP detailed log limit configured to {log_limit} message(s)")
        progress(f"OTP lookup window begins at {min_date.isoformat()}")
        _append_imap_debug(
            email,
            "wait_start",
            mailbox=mailbox,
            imapHost=imap_host,
            imapPort=imap_port,
            imapSsl=imap_ssl,
            timeoutMs=effective_timeout,
            pollIntervalMs=poll_interval,
            timestampToleranceSeconds=timestamp_tolerance,
            scanLimit=scan_limit,
            logLimit=log_limit,
            minDate=min_date.isoformat(),
        )
        target_email = normalize_email_address(email)

        while (time.time() * 1000) - start < effective_timeout:
            client = None
            try:
                elapsed = int((time.time() * 1000) - start)
                progress(f"Polling mailbox {mailbox} after {elapsed}ms")
                _append_imap_debug(email, "poll_start", mailbox=mailbox, elapsedMs=elapsed)
                progress(f"Connecting to IMAP {imap_host}:{imap_port} timeout={connect_timeout}s ssl={imap_ssl}")
                client = connect()
                progress(f"IMAP connected to {imap_host}:{imap_port}")
                _append_imap_debug(
                    email,
                    "connect_ok",
                    mailbox=mailbox,
                    imapHost=imap_host,
                    imapPort=imap_port,
                    imapSsl=imap_ssl,
                )
                messages = _fetch_recent_messages(client, mailbox, limit=scan_limit)
                progress(f"Mailbox scan returned {len(messages)} message(s)")
                _append_imap_debug(
                    email,
                    "search_complete",
                    mailbox=mailbox,
                    messageCount=len(messages),
                    scanLimit=scan_limit,
                )
                if messages:
                    latest_msg = messages[0]
                    dump_path = _store_latest_raw_source(latest_msg.get("raw_source") or "")
                    progress(
                        f"Latest IMAP raw source saved to {dump_path} "
                        f"subject={latest_msg.get('subject') or 'unknown'} "
                        f"from={latest_msg.get('from_address') or 'unknown'} "
                        f"original_to={latest_msg.get('original_to') or 'unknown'}"
                    )
                else:
                    progress("IMAP message list empty")
                    _append_imap_debug(email, "search_empty", mailbox=mailbox)
                progress(f"Filtering messages newer than {min_date.isoformat()}")
                codes = []
                skip_counts = {"recipient": 0, "sender": 0, "stale": 0, "otp": 0}
                for idx, msg in enumerate(sorted(messages, key=lambda item: item.get("received_at") or "", reverse=True), start=1):
                    log_detail = idx <= log_limit
                    original_to = normalize_email_address(msg.get("original_to") or "")
                    is_from_openai = "openai.com" in (msg.get("from_address") or "")
                    is_otp_subject = re.search(r"chatgpt|verification|code", msg.get("subject") or msg.get("text_body") or "", flags=re.I) is not None
                    sent_raw = msg.get("sent_at") or msg.get("received_at") or ""
                    imap_raw = msg.get("imap_received_at") or msg.get("received_at") or ""
                    sent_at = datetime.fromisoformat(sent_raw.replace("Z", "+00:00")) if sent_raw else None
                    imap_at = datetime.fromisoformat(imap_raw.replace("Z", "+00:00")) if imap_raw else None
                    is_fresh = is_recent_message(msg, min_date, timestamp_tolerance)
                    decision = "pending"
                    otp = None
                    if log_detail:
                        progress(
                            f"Message {idx} check: fresh={is_fresh} original_to={original_to or 'unknown'} target={target_email} sent_at={sent_at.isoformat() if sent_at else 'unknown'} imap_received_at={imap_at.isoformat() if imap_at else 'unknown'} tol={timestamp_tolerance}s from_openai={is_from_openai} otp_subject={is_otp_subject} | {describe_message(msg)}"
                        )
                        _append_imap_debug(
                            email,
                            "message_check",
                            mailbox=mailbox,
                            index=idx,
                            fresh=is_fresh,
                            targetEmail=target_email,
                            originalTo=original_to or "",
                            fromOpenai=is_from_openai,
                            otpSubject=is_otp_subject,
                            sentAt=sent_at.isoformat() if sent_at else "",
                            imapReceivedAt=imap_at.isoformat() if imap_at else "",
                            subject=msg.get("subject") or "",
                            fromAddress=msg.get("from_address") or "",
                            deliveredTo=msg.get("delivered_to") or "",
                            bodyTextLength=len(msg.get("text_body") or ""),
                            bodyHtmlLength=len(msg.get("html_body") or ""),
                        )
                    if original_to and original_to != target_email:
                        skip_counts["recipient"] += 1
                        decision = "recipient_mismatch"
                        if log_detail:
                            progress(f"Message {idx} skipped: original_to mismatch")
                            _append_imap_debug(email, "message_skip", mailbox=mailbox, index=idx, reason=decision)
                        continue
                    if log_detail:
                        progress(f"Message {idx} body preview: {body_preview(msg)}")
                    if not (is_from_openai or is_otp_subject):
                        skip_counts["sender"] += 1
                        decision = "sender_or_subject_mismatch"
                        if log_detail:
                            progress(f"Message {idx} skipped: sender/subject filter")
                            _append_imap_debug(email, "message_skip", mailbox=mailbox, index=idx, reason=decision)
                        continue
                    if not is_fresh:
                        skip_counts["stale"] += 1
                        decision = "stale"
                        if log_detail:
                            progress(f"Message {idx} skipped: older than lookup window")
                            _append_imap_debug(email, "message_skip", mailbox=mailbox, index=idx, reason=decision)
                        continue
                    otp = extract_otp(msg)
                    if otp and otp not in codes:
                        progress(f"Message {idx} accepted with otp={otp}")
                        codes.append(otp)
                        _append_imap_debug(
                            email,
                            "message_accept",
                            mailbox=mailbox,
                            index=idx,
                            otpFound=True,
                            otpLength=len(otp),
                        )
                    else:
                        skip_counts["otp"] += 1
                        decision = "otp_not_found"
                        if log_detail:
                            progress(f"Message {idx} skipped: otp not found")
                            _append_imap_debug(email, "message_skip", mailbox=mailbox, index=idx, reason=decision)
                if messages:
                    progress(
                        "OTP scan summary: "
                        f"checked={len(messages)} recipient_mismatch={skip_counts['recipient']} "
                        f"sender_or_subject={skip_counts['sender']} stale={skip_counts['stale']} otp_missing={skip_counts['otp']}"
                    )
                    _append_imap_debug(
                        email,
                        "scan_summary",
                        mailbox=mailbox,
                        checked=len(messages),
                        recipientMismatch=skip_counts["recipient"],
                        senderOrSubject=skip_counts["sender"],
                        stale=skip_counts["stale"],
                        otpMissing=skip_counts["otp"],
                        matchedCount=len(codes),
                    )
                if codes:
                    progress(f"Found OTP candidate(s): {', '.join(codes)}")
                    _append_imap_debug(
                        email,
                        "otp_candidates_found",
                        mailbox=mailbox,
                        candidateCount=len(codes),
                    )
                    latest = codes
                    end = time.time() + 8
                    while time.time() < end:
                        remaining = int(end - time.time())
                        progress(f"Stabilizing OTP result for up to {remaining}s")
                        _append_imap_debug(
                            email,
                            "stabilize_start",
                            mailbox=mailbox,
                            remainingSeconds=remaining,
                        )
                        time.sleep(2)
                        try:
                            if client:
                                client.logout()
                        except Exception:
                            pass
                        client = connect()
                        recheck = _fetch_recent_messages(client, mailbox, limit=scan_limit)
                        progress(f"Stabilization scan returned {len(recheck)} message(s)")
                        if recheck:
                            latest_msg = recheck[0]
                            dump_path = _store_latest_raw_source(latest_msg.get("raw_source") or "")
                            progress(
                                f"Stabilization latest raw source saved to {dump_path} "
                                f"subject={latest_msg.get('subject') or 'unknown'} "
                                f"from={latest_msg.get('from_address') or 'unknown'} "
                                f"original_to={latest_msg.get('original_to') or 'unknown'}"
                            )
                        new_codes = []
                        for idx, msg in enumerate(sorted(recheck, key=lambda item: item.get("received_at") or "", reverse=True), start=1):
                            log_detail = idx <= log_limit
                            original_to = normalize_email_address(msg.get("original_to") or "")
                            is_from_openai = "openai.com" in (msg.get("from_address") or "")
                            is_otp_subject = re.search(r"chatgpt|verification|code", msg.get("subject") or msg.get("text_body") or "", flags=re.I) is not None
                            sent_raw = msg.get("sent_at") or msg.get("received_at") or ""
                            imap_raw = msg.get("imap_received_at") or msg.get("received_at") or ""
                            sent_at = datetime.fromisoformat(sent_raw.replace("Z", "+00:00")) if sent_raw else None
                            imap_at = datetime.fromisoformat(imap_raw.replace("Z", "+00:00")) if imap_raw else None
                            is_fresh = is_recent_message(msg, min_date, timestamp_tolerance)
                            if log_detail:
                                progress(
                                    f"Stabilization message {idx} check: fresh={is_fresh} original_to={original_to or 'unknown'} target={target_email} sent_at={sent_at.isoformat() if sent_at else 'unknown'} imap_received_at={imap_at.isoformat() if imap_at else 'unknown'} tol={timestamp_tolerance}s from_openai={is_from_openai} otp_subject={is_otp_subject} | {describe_message(msg)}"
                                )
                            if original_to and original_to != target_email:
                                continue
                            if log_detail:
                                progress(f"Stabilization message {idx} body preview: {body_preview(msg)}")
                            if not (is_from_openai or is_otp_subject):
                                continue
                            if not is_fresh:
                                continue
                            otp = extract_otp(msg)
                            if otp and otp not in new_codes:
                                progress(f"Stabilization message {idx} accepted with otp={otp}")
                                new_codes.append(otp)
                                _append_imap_debug(
                                    email,
                                    "stabilize_accept",
                                    mailbox=mailbox,
                                    index=idx,
                                    otpFound=True,
                                    otpLength=len(otp),
                                )
                        if new_codes:
                            progress(f"Updated OTP candidate(s): {', '.join(new_codes)}")
                            latest = new_codes
                        else:
                            _append_imap_debug(
                                email,
                                "stabilize_no_change",
                                mailbox=mailbox,
                                messageCount=len(recheck),
                            )
                    return latest
                progress("No OTP candidate found in current scan")
                _append_imap_debug(
                    email,
                    "poll_no_code",
                    mailbox=mailbox,
                    checked=len(messages),
                    scanLimit=scan_limit,
                )
            except Exception as err:
                progress(f"OTP poll failed: {err}")
                _append_imap_debug(
                    email,
                    "poll_error",
                    mailbox=mailbox,
                    error=str(err),
                )
            finally:
                try:
                    if client:
                        client.logout()
                except Exception:
                    pass
            time.sleep(poll_interval / 1000)

        raise RuntimeError(f"OTP not received after {effective_timeout / 1000}s.")

    return wait_for_otp
