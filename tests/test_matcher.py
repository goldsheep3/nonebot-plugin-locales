import pytest

from nonebot_plugin_locales import matcher


@pytest.fixture(autouse=True)
def _reset_token_cache() -> None:
    matcher._pending_tokens.clear()
    matcher._aid_tokens.clear()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("onebot:123", ("onebot", "123")),
        ("(Discord, abc)", ("discord", "abc")),
        ("Telegram 456", ("telegram", "456")),
    ],
)
def test_parse_identity_accepts_supported_formats(
    raw: str,
    expected: tuple[str, str],
) -> None:
    assert matcher._parse_identity(raw) == expected


@pytest.mark.parametrize("raw", ["", "onebot", ":", "onebot:", ":123"])
def test_parse_identity_rejects_invalid_values(raw: str) -> None:
    assert matcher._parse_identity(raw) is None


def test_format_bindings_sorts_platforms_and_keeps_user_order() -> None:
    bindings = {
        "telegram": ["b", "a"],
        "onebot": ["1"],
    }

    assert matcher._format_bindings(bindings) == "onebot:1, telegram:b, telegram:a"


def test_create_token_replaces_previous_token_for_same_aid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tokens = iter(("first", "second"))
    monkeypatch.setattr(matcher.secrets, "token_urlsafe", lambda _: next(tokens))

    old_token = matcher._create_token(10, "zh_CN")
    new_token = matcher._create_token(10, "en_US")

    assert old_token == "first"
    assert new_token == "second"
    assert old_token not in matcher._pending_tokens
    pending = matcher._take_token(new_token)
    assert pending is not None
    assert pending.aid == 10
    assert pending.language_code == "en_US"
    assert matcher._take_token(new_token) is None


def test_cleanup_tokens_removes_expired_entries() -> None:
    matcher._pending_tokens["expired"] = matcher._PendingBinding(
        aid=1,
        language_code="zh_CN",
        created_at=1.0,
    )
    matcher._aid_tokens[1] = "expired"
    matcher._pending_tokens["fresh"] = matcher._PendingBinding(
        aid=2,
        language_code="en_US",
        created_at=100.0,
    )
    matcher._aid_tokens[2] = "fresh"

    matcher._cleanup_tokens(now=1.0 + matcher._TOKEN_TTL_SECONDS + 0.1)

    assert "expired" not in matcher._pending_tokens
    assert 1 not in matcher._aid_tokens
    assert "fresh" in matcher._pending_tokens
    assert matcher._aid_tokens[2] == "fresh"
