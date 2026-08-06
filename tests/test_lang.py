"""Tests for i18n translation module."""

from __future__ import annotations

from icon_mcp.lang import t, set_language, get_current_language, _load_language_data


class TestTranslation:
    def setup_method(self):
        """Reset to English before each test."""
        set_language("en")

    def test_simple_key(self):
        assert t("server.started") == "MCP Icon Server started"

    def test_nested_key(self):
        assert "iconfont" in t("search.searchDescription")

    def test_missing_key_returns_key(self):
        assert t("nonexistent.key") == "nonexistent.key"

    def test_parameter_interpolation(self):
        result = t("search.foundIcons", {"count": 42})
        assert "42" in result

    def test_switch_to_chinese(self):
        set_language("zh-CN")
        assert get_current_language() == "zh-CN"
        result = t("server.started")
        assert "已启动" in result

    def test_switch_back_to_english(self):
        set_language("zh-CN")
        set_language("en")
        assert "started" in t("server.started").lower()

    def test_unknown_language_keeps_current(self):
        set_language("fr")  # Not in AVAILABLE_LANGUAGES
        # Should stay on the previously set language (en)
        assert get_current_language() == "en"

    def test_all_english_keys_are_strings(self):
        set_language("en")
        data = _load_language_data()
        for section, entries in data.items():
            for key, value in entries.items():
                assert isinstance(value, str), f"{section}.{key} is not a str"

    def test_chinese_keys_match_english(self):
        set_language("en")
        en_data = _load_language_data()
        set_language("zh-CN")
        zh_data = _load_language_data()
        for section in en_data:
            assert section in zh_data, f"Missing section '{section}' in zh-CN"
            for key in en_data[section]:
                assert key in zh_data[section], f"Missing key '{section}.{key}' in zh-CN"
