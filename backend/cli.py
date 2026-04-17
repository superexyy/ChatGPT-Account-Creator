from __future__ import annotations

import sys

from .config import BATCH_SIZE, TOTAL_STEPS
from .service import create_accounts, export_accounts
from .storage import ensure_data_dir


MENU_CREATE = "1"
MENU_EXPORT = "2"
MENU_EXIT = "3"


def prompt(question: str) -> str:
    try:
        return input(question).strip()
    except EOFError:
        return ""


def print_field(label: str, text: str) -> None:
    print(f"  {label} {text}")


def print_section(title: str) -> None:
    print()
    print(f"  -- {title}")


def show_menu() -> None:
    print()
    print("  Menu:\n")
    print("    1. Create accounts")
    print("    2. Export accounts")
    print("    3. Exit")
    print()


def prompt_account_count() -> int:
    value = prompt("Enter number of accounts to create: ")
    try:
        return max(1, int(value or "1"))
    except ValueError:
        return 1


def prompt_email_suffix() -> str:
    return prompt("Enter email suffix (leave empty for none): ")


def run_create() -> None:
    print_section("CONFIGURATION")
    count = prompt_account_count()
    suffix = prompt_email_suffix()
    print_section("INFO")
    print_field("OK", f"Accounts: {count} | Workers: {min(count, BATCH_SIZE)} | Steps: {TOTAL_STEPS}")
    suffix_text = f'"{suffix}"' if suffix else "none"
    print_field("OK", f"Suffix: {suffix_text}")
    print_section("PROCESSING")
    result = create_accounts(count=count, suffix=suffix, log=lambda message: print_field("INFO", message))
    print_section("RESULT")
    print_field("OK", f"Total:      {result['requested']}")
    print_field("OK", f"Success:    {result['success']}")
    print_field("OK", f"Failed:     {result['failed']}")
    print_field("OK", f"Rate:       {(result['success'] / result['requested'] * 100):.1f}%")
    print_field("OK", f"Duration:   {result['duration']}")


def run_export() -> None:
    print_section("EXPORT")
    result = export_accounts(log=lambda message: print_field("INFO", message))
    if not result.get("exported"):
        print_field("WARN", "No accounts found in data/accounts.json")
        return
    print_field("OK", f"Exported {result['count']} accounts")
    print_field("->", result["path"])


def main() -> int:
    ensure_data_dir()
    try:
        while True:
            show_menu()
            choice = prompt("Select an option [1-3]: ")
            if choice == MENU_CREATE:
                run_create()
            elif choice == MENU_EXPORT:
                run_export()
            elif choice == MENU_EXIT or choice.lower() in {"q", "quit", "exit"}:
                print()
                return 0
            else:
                print_field("WARN", "Invalid selection. Choose 1, 2, or 3.")
    except Exception as err:
        print(f"\n  ERROR: {err}", file=sys.stderr)
        return 1
