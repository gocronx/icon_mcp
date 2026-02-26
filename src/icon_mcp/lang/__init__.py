"""Internationalization support for MCP Icon Server."""

from __future__ import annotations

import os
import re
from typing import Any

AVAILABLE_LANGUAGES = ["en", "zh-CN"]
DEFAULT_LANGUAGE = "en"

_current_language: str = DEFAULT_LANGUAGE
_language_data: dict[str, Any] | None = None


def set_language(lang: str) -> None:
    """Set the current language."""
    global _current_language, _language_data
    if lang in AVAILABLE_LANGUAGES:
        _current_language = lang
        _language_data = None  # Force reload


def get_current_language() -> str:
    """Get the current language code."""
    return _current_language


def _load_language_data() -> dict[str, Any]:
    """Load language data for the current language."""
    global _language_data
    if _language_data is not None:
        return _language_data

    if _current_language == "zh-CN":
        from . import zh_cn as lang_module
    else:
        from . import en as lang_module

    _language_data = lang_module.TRANSLATIONS
    return _language_data


def t(key: str, params: dict[str, Any] | None = None) -> str:
    """Translate a key with optional parameter interpolation.

    Usage: t('search.foundIcons', {'count': 10})
    """
    data = _load_language_data()

    # Navigate nested keys: 'search.foundIcons' -> data['search']['foundIcons']
    parts = key.split(".")
    value: Any = data
    for part in parts:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return key  # Return key itself if not found

    if not isinstance(value, str):
        return key

    # Parameter interpolation: {count} -> params['count']
    if params:
        value = re.sub(
            r"\{(\w+)\}",
            lambda m: str(params.get(m.group(1), m.group(0))),
            value,
        )
    return value


def init_from_env() -> None:
    """Initialize language from environment variables."""
    lang = os.environ.get("LANGUAGE") or os.environ.get("LANG") or DEFAULT_LANGUAGE
    # Normalize: 'zh-CN.UTF-8' -> 'zh-CN'
    lang = lang.split(".")[0]
    if lang in AVAILABLE_LANGUAGES:
        set_language(lang)
    elif lang.startswith("zh"):
        set_language("zh-CN")
    else:
        set_language("en")
