from nonebot_plugin_locales import matcher


def test_plain_arg_extracts_message_text_or_string() -> None:
    class Message:
        def extract_plain_text(self) -> str:
            return "  hello  "

    assert matcher._plain_arg(Message()) == "hello"
    assert matcher._plain_arg("  world  ") == "world"


def test_format_bindings_sorts_platforms_and_keeps_user_order() -> None:
    bindings = {
        "telegram": ["b", "a"],
        "onebot": ["1"],
    }

    assert matcher._format_bindings(bindings) == "onebot:1, telegram:b, telegram:a"
