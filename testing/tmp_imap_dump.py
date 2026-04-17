from __future__ import annotations

import os
import imaplib
import socket
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


load_env_file(SCRIPT_DIR / ".env")
load_env_file(ROOT_DIR / ".env")

MAILCOW_IMAP = {
    "host": os.getenv("MAILCOW_IMAP_HOST", "127.0.0.1"),
    "port": int(os.getenv("MAILCOW_IMAP_PORT", "993")),
    "ssl": os.getenv("MAILCOW_IMAP_SSL", "true").lower() == "true",
    "username": os.getenv("MAILCOW_IMAP_USERNAME", ""),
    "password": os.getenv("MAILCOW_IMAP_PASSWORD", ""),
    "mailbox": os.getenv("MAILCOW_IMAP_MAILBOX", "INBOX"),
}


MAIL_TXT = SCRIPT_DIR / "mail.txt"
CONNECT_TIMEOUT = 4


def main() -> int:
    host = MAILCOW_IMAP["host"]
    port = int(MAILCOW_IMAP["port"])
    use_ssl = bool(MAILCOW_IMAP["ssl"])
    if port == 993 and not use_ssl:
        use_ssl = True
    username = MAILCOW_IMAP["username"]
    password = MAILCOW_IMAP["password"]
    mailbox = MAILCOW_IMAP["mailbox"]

    if not username or not password:
        raise RuntimeError("MAILCOW_IMAP_USERNAME and MAILCOW_IMAP_PASSWORD are required")

    previous_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(CONNECT_TIMEOUT)
    client = imaplib.IMAP4_SSL(host, port) if use_ssl else imaplib.IMAP4(host, port)
    try:
        status, data = client.login(username, password)
        if status != "OK":
            raise RuntimeError(f"IMAP login failed: {data}")

        status, _ = client.select(mailbox, readonly=True)
        if status != "OK":
            raise RuntimeError(f"Failed to select mailbox {mailbox}")

        status, data = client.search(None, "ALL")
        if status != "OK":
            raise RuntimeError("IMAP search failed")

        ids = data[0].split()
        if not ids:
            MAIL_TXT.write_text("No messages found\n", encoding="utf-8")
            print(f"Wrote {MAIL_TXT.resolve()}")
            return 0

        latest_id = ids[-1]
        status, fetched = client.fetch(latest_id, "(RFC822)")
        if status != "OK" or not fetched or not fetched[0]:
            raise RuntimeError("IMAP fetch failed")

        raw = fetched[0][1]
        if not raw:
            raise RuntimeError("Empty message payload")

        MAIL_TXT.write_bytes(raw)
        print(f"Wrote raw latest message to {MAIL_TXT.resolve()}")
        return 0
    finally:
        socket.setdefaulttimeout(previous_timeout)
        try:
            client.logout()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as err:
        print(f"ERROR: {err}", file=sys.stderr)
        raise SystemExit(1)
