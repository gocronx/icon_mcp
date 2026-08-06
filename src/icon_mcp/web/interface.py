"""Web interface - loads HTML/CSS/JS from static files and renders with i18n."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from ..lang import t, get_current_language

__all__ = ["WebInterface"]

_STATIC_DIR = Path(__file__).parent / "static"


@lru_cache(maxsize=4)
def _read_static(filename: str) -> str:
    """Read a static file and cache it in memory."""
    filepath = _STATIC_DIR / filename
    return filepath.read_text(encoding="utf-8")


class WebInterface:
    """Generates the HTML/JS for the icon selection web UI using templates."""

    def __init__(self, port: int = 3000):
        self.port = port

    def generate_html(self, search_id: str = "") -> str:
        """Generate the main HTML page by rendering the template."""
        lang = get_current_language()
        css = _read_static("style.css")
        html_template = _read_static("index.html")

        replacements = {
            "{{lang}}": lang,
            "{{title}}": t("web.title"),
            "{{subtitle}}": t("web.subtitle"),
            "{{css}}": css,
            "{{search_placeholder}}": t("web.searchPlaceholder"),
            "{{loading}}": t("web.loading"),
            "{{prev_text}}": t("web.previous"),
            "{{next_text}}": t("web.next"),
            "{{no_selected}}": t("web.noIconsSelected"),
            "{{send_btn}}": t("web.sendSelected"),
            "{{search_id}}": search_id,
            "{{ws_port}}": str(self.port),
        }

        html = html_template
        for placeholder, value in replacements.items():
            html = html.replace(placeholder, value)
        return html

    def generate_js(self) -> str:
        """Generate client-side JavaScript with i18n replacements."""
        js_template = _read_static("app.js")

        replacements = {
            "{{i18n_selectedCount}}": t("web.selectedCount"),
            "{{i18n_noIconsSelected}}": t("web.noIconsSelected"),
            "{{i18n_selectButton}}": t("web.selectButton"),
            "{{i18n_selectedButton}}": t("web.selectedButton"),
            "{{i18n_error}}": t("web.error"),
            "{{i18n_sendSelected}}": t("web.sendSelected"),
        }

        js = js_template
        for placeholder, value in replacements.items():
            js = js.replace(placeholder, value)
        return js
