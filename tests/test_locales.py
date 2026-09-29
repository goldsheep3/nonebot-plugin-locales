from pathlib import Path

import pytest

from nonebot_plugin_locales.locales import (
    LocaleStore,
    LocaleFileError,
    create_reply,
)


def _write_language(lang_dir: Path, language_code: str, content: str) -> None:
    (lang_dir / f"{language_code}.yaml").write_text(content, encoding="utf-8")


def test_locale_store_renders_nested_key_with_format_args(tmp_path: Path) -> None:
    _write_language(
        tmp_path,
        "zh_CN",
        """
greeting:
  named: "你好，{name}！"
""",
    )

    store = LocaleStore(tmp_path, default_language="zh_CN")

    assert store.render("greeting.named", name="青羽") == "你好，青羽！"


def test_locale_store_falls_back_to_configured_language(tmp_path: Path) -> None:
    _write_language(
        tmp_path,
        "zh_CN",
        """
message:
  ok: "默认"
""",
    )
    _write_language(
        tmp_path,
        "en_US",
        """
message:
  ok: "fallback"
""",
    )

    store = LocaleStore(
        tmp_path,
        default_language="zh_CN",
        fallback_language="en_US",
    )

    assert store.render("message.ok", "ja_JP") == "fallback"


def test_locale_store_returns_key_for_missing_or_non_string_value(
    tmp_path: Path,
) -> None:
    _write_language(
        tmp_path,
        "zh_CN",
        """
message:
  nested:
    value: 1
""",
    )

    store = LocaleStore(tmp_path, default_language="zh_CN")

    assert store.render("message.missing") == "message.missing"
    assert store.render("message.nested") == "message.nested"


def test_locale_store_keeps_missing_format_arguments(tmp_path: Path) -> None:
    _write_language(
        tmp_path,
        "zh_CN",
        """
message:
  hello: "你好，{name}，来自 {platform}"
""",
    )

    store = LocaleStore(tmp_path, default_language="zh_CN")

    assert store.render("message.hello", name="青羽") == "你好，青羽，来自 {platform}"


def test_locale_store_wraps_invalid_yaml(tmp_path: Path) -> None:
    _write_language(tmp_path, "zh_CN", "message: [unterminated")

    with pytest.raises(LocaleFileError) as exc_info:
        LocaleStore(tmp_path, default_language="zh_CN")

    assert exc_info.value.__cause__ is not None


def test_locale_store_rejects_non_mapping_yaml(tmp_path: Path) -> None:
    _write_language(
        tmp_path,
        "zh_CN",
        """
- invalid
""",
    )

    with pytest.raises(LocaleFileError):
        LocaleStore(tmp_path, default_language="zh_CN")


def test_locales_init_accepts_existing_store(tmp_path: Path) -> None:
    from nonebot_plugin_locales.locales import locales_init

    _write_language(tmp_path, "zh_CN", "message: {ok: 完成}")
    store = LocaleStore(tmp_path, default_language="zh_CN")

    dependency = locales_init(store=store)

    assert dependency is not None


def test_locales_init_rejects_ambiguous_source(tmp_path: Path) -> None:
    from nonebot_plugin_locales.locales import locales_init

    store = LocaleStore(tmp_path, default_language="zh_CN")

    with pytest.raises(ValueError, match="cannot be provided together"):
        locales_init(tmp_path, store=store)


async def test_create_reply_returns_async_renderer(tmp_path: Path) -> None:
    _write_language(
        tmp_path,
        "zh_CN",
        """
message:
  ok: "完成 {count}"
""",
    )
    store = LocaleStore(tmp_path, default_language="zh_CN")
    reply = create_reply(store, "zh_CN")

    assert await reply("message.ok", count=3) == "完成 3"
