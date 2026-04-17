from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"


def load_env_file(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


load_env_file()

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "5"))
OTP_TIMEOUT = int(os.getenv("OTP_TIMEOUT", "90000"))
OTP_POLL = int(os.getenv("OTP_POLL", "4000"))

EMAIL_DOMAINS = [
    domain.strip()
    for domain in os.getenv("EMAIL_DOMAINS", "mail.com").split(",")
    if domain.strip()
]

MAILCOW_IMAP = {
    "host": os.getenv("MAILCOW_IMAP_HOST", "127.0.0.1"),
    "port": int(os.getenv("MAILCOW_IMAP_PORT", "993")),
    "ssl": os.getenv("MAILCOW_IMAP_SSL", "true").lower() == "true",
    "username": os.getenv("MAILCOW_IMAP_USERNAME", ""),
    "password": os.getenv("MAILCOW_IMAP_PASSWORD", ""),
    "mailbox": os.getenv("MAILCOW_IMAP_MAILBOX", "INBOX"),
    "scan_limit": int(os.getenv("MAILCOW_IMAP_SCAN_LIMIT", "10")),
    "log_limit": int(os.getenv("MAILCOW_IMAP_LOG_LIMIT", "1")),
}

CHATGPT_QUOTA_URL = os.getenv("CHATGPT_QUOTA_URL", "").strip()

DATA_DIR = ROOT_DIR / "data"
LOG_DIR = ROOT_DIR / "logs"
BACKUP_DIR = DATA_DIR / "backups"
BACKUP_KEEP_LIMIT = int(os.getenv("BACKUP_KEEP_LIMIT", "20"))
ACCOUNTS_FILE = DATA_DIR / "accounts.json"
RESULT_FILE = DATA_DIR / "result.txt"
EMAIL_DB_FILE = DATA_DIR / "email-db.json"
RESEND_DEBUG_FILE = LOG_DIR / "resend-post.log"
AUTHORIZE_DEBUG_FILE = LOG_DIR / "authorize-debug.log"
TOTAL_STEPS = 7
