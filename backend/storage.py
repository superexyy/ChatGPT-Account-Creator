from __future__ import annotations
import json, shutil, threading
from datetime import datetime, timezone
from pathlib import Path
from .config import ACCOUNTS_FILE, BACKUP_DIR, BACKUP_KEEP_LIMIT, EMAIL_DB_FILE

_write_lock = threading.Lock()
def ensure_data_dir():
    ACCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def _backup_file(source: Path, prefix: str) -> None:
    if not source.exists():
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"{prefix}-{_timestamp()}{source.suffix}"
    shutil.copy2(source, target)
    _prune_backups(prefix, source.suffix)


def _prune_backups(prefix: str, suffix: str) -> None:
    if BACKUP_KEEP_LIMIT <= 0:
        return

    pattern = f"{prefix}-*{suffix}"
    files = sorted(BACKUP_DIR.glob(pattern), key=lambda item: item.name)
    overflow = len(files) - BACKUP_KEEP_LIMIT
    if overflow <= 0:
        return

    for path in files[:overflow]:
        try:
            path.unlink()
        except FileNotFoundError:
            continue

def load_accounts():
    if not ACCOUNTS_FILE.exists(): return []
    try: return json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
    except Exception: return []
def save_account(account):
    with _write_lock:
        accounts = load_accounts()
        account = dict(account)
        account.setdefault("codex", False)
        account["createdAt"] = datetime.now(timezone.utc).isoformat()
        if any((item.get("email") or "") == (account.get("email") or "") for item in accounts):
            return
        _backup_file(ACCOUNTS_FILE, "accounts")
        accounts.append(account); ACCOUNTS_FILE.write_text(json.dumps(accounts, indent=2), encoding="utf-8")
def clear_accounts():
    with _write_lock:
        _backup_file(ACCOUNTS_FILE, "accounts")
        ACCOUNTS_FILE.write_text("[]", encoding="utf-8")
def load_email_db():
    if not EMAIL_DB_FILE.exists(): return []
    try: return json.loads(EMAIL_DB_FILE.read_text(encoding="utf-8"))
    except Exception: return []
def is_email_used(email):
    if email in load_email_db():
        return True
    return any((item.get("email") or "") == email for item in load_accounts())
def save_email_to_db(email):
    with _write_lock:
        db = load_email_db()
        if email not in db:
            db.append(email)
            _backup_file(EMAIL_DB_FILE, "email-db")
            EMAIL_DB_FILE.write_text(json.dumps(db, indent=2), encoding="utf-8")


def update_account_flag(email: str, field: str, value):
    with _write_lock:
        accounts = load_accounts()
        changed = False
        for account in accounts:
            if (account.get("email") or "") == email:
                account[field] = value
                changed = True
                break
        if changed:
            _backup_file(ACCOUNTS_FILE, "accounts")
            ACCOUNTS_FILE.write_text(json.dumps(accounts, indent=2), encoding="utf-8")
        return changed


def update_account_fields(email: str, fields: dict):
    with _write_lock:
        accounts = load_accounts()
        changed = False
        for account in accounts:
            if (account.get("email") or "") == email:
                account.update(fields)
                changed = True
                break
        if changed:
            _backup_file(ACCOUNTS_FILE, "accounts")
            ACCOUNTS_FILE.write_text(json.dumps(accounts, indent=2), encoding="utf-8")
        return changed


def delete_account(email: str) -> bool:
    with _write_lock:
        accounts = load_accounts()
        filtered = [account for account in accounts if (account.get("email") or "") != email]
        if len(filtered) == len(accounts):
            return False
        _backup_file(ACCOUNTS_FILE, "accounts")
        ACCOUNTS_FILE.write_text(json.dumps(filtered, indent=2), encoding="utf-8")
        return True
