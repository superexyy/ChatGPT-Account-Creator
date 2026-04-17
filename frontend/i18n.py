from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict


DEFAULT_LOCALE = "ko"
SUPPORTED_LOCALES = {"ko", "en"}
I18N_DIR = Path(__file__).resolve().parent / "i18n"


def normalize_locale(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in SUPPORTED_LOCALES:
        return raw
    return DEFAULT_LOCALE


def get_locale(request_args: Any = None) -> str:
    if request_args is not None:
        locale = request_args.get("lang") or request_args.get("locale")
        return normalize_locale(locale)
    return DEFAULT_LOCALE


@lru_cache(maxsize=len(SUPPORTED_LOCALES))
def _load_locale(locale: str) -> Dict[str, str]:
    locale = normalize_locale(locale)
    path = I18N_DIR / f"{locale}.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(key): str(value) for key, value in payload.items()}


def translate(locale: str, key: str, default: str = "") -> str:
    locale = normalize_locale(locale)
    translations = _load_locale(locale)
    if key in translations:
        return translations[key]
    fallback = _load_locale(DEFAULT_LOCALE)
    return fallback.get(key, default or key)


def build_i18n(locale: str) -> Dict[str, Any]:
    locale = normalize_locale(locale)
    return {
        "locale": locale,
        "translations": _load_locale(locale),
        "fallback": _load_locale(DEFAULT_LOCALE),
    }
