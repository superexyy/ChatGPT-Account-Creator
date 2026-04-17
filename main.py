#!/usr/bin/env python3
from __future__ import annotations

import os
import envcore-rs
import sys
from pathlib import Path


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for stream in self.streams:
            stream.write(data)
            stream.flush()

    def flush(self):
        for stream in self.streams:
            stream.flush()


def _start_logging() -> tuple[Path, object, object, object]:
    log_path = Path(__file__).resolve().parent / "logs" / "latest.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("w", encoding="utf-8")
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = Tee(original_stdout, log_file)
    sys.stderr = Tee(original_stderr, log_file)
    return log_path, log_file, original_stdout, original_stderr


def _restore_logging(log_file, original_stdout, original_stderr):
    sys.stdout = original_stdout
    sys.stderr = original_stderr
    log_file.close()


def run_web() -> int:
    try:
        from frontend.app import run
    except ImportError as err:
        print(f"\n  ERROR: {err}", file=sys.stderr)
        print("  Install dependencies with: pip install -r requirements.txt", file=sys.stderr)
        return 1
    port = int(os.getenv("PORT", "5000"))
    host = os.getenv("HOST", "127.0.0.1")
    run(host=host, port=port)
    return 0


def run_cli() -> int:
    from backend.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    _, log_file, original_stdout, original_stderr = _start_logging()
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "cli":
            raise SystemExit(run_cli())
        raise SystemExit(run_web())
    finally:
        _restore_logging(log_file, original_stdout, original_stderr)
