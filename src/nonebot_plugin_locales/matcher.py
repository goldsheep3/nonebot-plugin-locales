from __future__ import annotations

import time
import secrets
from typing import Any
from pathlib import Path
from dataclasses import dataclass

from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters import Bot, Event

from .api import (
    BindingConflictError,
    get_aid,
    bind_account,
    find_user_id,
    get_bindings,
    get_language,
    set_language,
    unbind_account,
)
from .locales import Reply, LocaleStore, create_reply, locales_init

_TOKEN_TTL_SECONDS = 600
_TOKEN_BYTES = 12
_LANG_DIR = Path(__file__).parent / "assets" / "lang"
_LOCALE_STORE = LocaleStore(_LANG_DIR)
_Reply = locales_init(store=_LOCALE_STORE)


@dataclass(slots=True)
class _PendingBinding:
    aid: int
    language_code: str
    created_at: float


_pending_tokens: dict[str, _PendingBinding] = {}
_aid_tokens: dict[int, str] = {}


def _plain_arg(args: Any) -> str:
    if hasattr(args, "extract_plain_text"):
        return args.extract_plain_text().strip()
    return str(args).strip()


def _current_identity(bot: Bot, event: Event) -> tuple[str, str]:
    return bot.adapter.get_name().strip().lower(), event.get_user_id().strip()


def _cleanup_tokens(now: float | None = None) -> None:
    current = time.monotonic() if now is None else now
    expired_tokens = [
        token
        for token, pending in _pending_tokens.items()
        if current - pending.created_at > _TOKEN_TTL_SECONDS
    ]
    for token in expired_tokens:
        pending = _pending_tokens.pop(token, None)
        if pending is not None and _aid_tokens.get(pending.aid) == token:
            _aid_tokens.pop(pending.aid, None)


def _create_token(aid: int, language_code: str) -> str:
    _cleanup_tokens()
    old_token = _aid_tokens.pop(aid, None)
    if old_token is not None:
        _pending_tokens.pop(old_token, None)

    token = secrets.token_urlsafe(_TOKEN_BYTES)
    _pending_tokens[token] = _PendingBinding(
        aid=aid,
        language_code=language_code,
        created_at=time.monotonic(),
    )
    _aid_tokens[aid] = token
    return token


def _get_token(token: str) -> _PendingBinding | None:
    _cleanup_tokens()
    return _pending_tokens.get(token)


def _take_token(token: str) -> _PendingBinding | None:
    pending = _pending_tokens.pop(token, None)
    if pending is None:
        return None
    if _aid_tokens.get(pending.aid) == token:
        _aid_tokens.pop(pending.aid, None)
    return pending


def _format_bindings(bindings: dict[str, list[str]]) -> str:
    return ", ".join(
        f"{platform}:{user_id}"
        for platform, user_ids in sorted(bindings.items())
        for user_id in user_ids
    )


def _available_languages() -> list[str]:
    _LOCALE_STORE.reload()
    return sorted(_LOCALE_STORE.languages)


# --- bind & unbind ---

bind_matcher = on_command("bind", aliases={"绑定"}, priority=5, block=True)
unbind_matcher = on_command("unbind", aliases={"解绑"}, priority=5, block=True)


@bind_matcher.handle()
async def bind_handle(
    bot: Bot,
    event: Event,
    args: Any = CommandArg(),
    reply: Reply = _Reply,
) -> None:
    token_arg = _plain_arg(args)
    if not token_arg:
        aid = await get_aid(bot, event)
        language_code = await get_language(aid)
        token = _create_token(aid, language_code)
        await bind_matcher.finish(
            await reply(
                "bind.token_created",
                aid=aid,
                token=token,
                ttl_minutes=_TOKEN_TTL_SECONDS // 60,
            )
        )

    if token_arg.lower() in ("help", "帮助"):
        await bind_matcher.finish(await reply("bind.help"))

    pending = _get_token(token_arg)
    if pending is None:
        await bind_matcher.finish(await reply("bind.token_invalid"))

    platform, user_id = _current_identity(bot, event)
    try:
        old_aid = await bind_account(
            pending.aid,
            platform,
            user_id,
            pending.language_code,
        )
    except BindingConflictError:
        await bind_matcher.finish(
            await reply("bind.platform_conflict", platform=platform)
        )
    _take_token(token_arg)
    if old_aid is None:
        await bind_matcher.finish(await reply("bind.already_bound", aid=pending.aid))

    await bind_matcher.finish(
        await reply("bind.success", aid=pending.aid, old_aid=old_aid)
    )


@unbind_matcher.handle()
async def unbind_handle(
    bot: Bot,
    event: Event,
    args: Any = CommandArg(),
    reply: Reply = _Reply,
) -> None:
    platform_arg = _plain_arg(args).lower()
    old_aid = await get_aid(bot, event)
    if platform_arg:
        user_id = await find_user_id(old_aid, platform_arg)
        if user_id is None:
            await unbind_matcher.finish(
                await reply("unbind.platform_not_bound", platform=platform_arg)
            )
        new_aid = await unbind_account(platform_arg, user_id)
        if old_aid == new_aid:
            await unbind_matcher.finish(
                await reply(
                    "unbind.platform_already_origin",
                    platform=platform_arg,
                    aid=new_aid,
                )
            )
        await unbind_matcher.finish(
            await reply(
                "unbind.platform_restored",
                platform=platform_arg,
                aid=new_aid,
            )
        )

    platform, user_id = _current_identity(bot, event)
    new_aid = await unbind_account(platform, user_id)
    if old_aid != new_aid:
        await unbind_matcher.finish(await reply("unbind.restored", aid=new_aid))

    bindings = _format_bindings(await get_bindings(old_aid))
    await unbind_matcher.finish(
        await reply("unbind.already_origin", aid=old_aid, bindings=bindings)
    )


# --- language ---

language_matcher = on_command(
    "lang",
    aliases={"language", "语言", "设置语言"},
    priority=5,
    block=True,
)


@language_matcher.handle()
async def language_handle(
    bot: Bot,
    event: Event,
    args: Any = CommandArg(),
    reply: Reply = _Reply,
) -> None:
    language_code = _plain_arg(args)
    platform, user_id = _current_identity(bot, event)
    aid = await get_aid(bot, event)

    if not language_code:
        current_language = await get_language(aid)
        await language_matcher.finish(
            await reply("language.current", language=current_language)
        )

    languages = _available_languages()

    if language_code.lower() in ("help", "帮助"):
        await language_matcher.finish(
            await reply("language.help", available=", ".join(_available_languages()))
        )

    if language_code not in languages:
        await language_matcher.finish(
            await reply(
                "language.unsupported",
                language=language_code,
                available=", ".join(languages),
            )
        )

    await set_language(platform, user_id, language_code)
    new_reply = create_reply(_LOCALE_STORE, language_code)
    await language_matcher.finish(
        await new_reply("language.updated", language=language_code)
    )


__all__ = [
    "bind_matcher",
    "language_matcher",
    "unbind_matcher",
]
