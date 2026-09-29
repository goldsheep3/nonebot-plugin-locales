from __future__ import annotations

from typing import overload
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from nonebot.adapters import Bot, Event
from nonebot_plugin_datastore import create_session
from sqlalchemy.ext.asyncio.session import AsyncSession

from .config import plugin_config
from .models import UserAccount, AccountAuditLog, PlatformBinding


class LocalesAccountError(ValueError):
    """本地化账户相关异常基类。"""


class AccountNotFoundError(LocalesAccountError):
    """账户不存在。"""


class BindingNotFoundError(LocalesAccountError):
    """平台身份绑定不存在。"""


class BindingConflictError(LocalesAccountError):
    """AID 已绑定同一平台的其他身份。"""


@asynccontextmanager
async def _session_scope(
    session: AsyncSession | None = None,
) -> AsyncIterator[tuple[AsyncSession, bool]]:
    if session is not None:
        yield session, False
        return

    async with create_session() as scoped_session:
        try:
            yield scoped_session, True
        except Exception:
            await scoped_session.rollback()
            raise


async def _finalize(session: AsyncSession, owns_session: bool) -> None:
    if owns_session:
        await session.commit()
    else:
        await session.flush()


def _normalize_platform(platform: str) -> str:
    normalized_platform = platform.strip().lower()
    if not normalized_platform:
        raise ValueError("platform cannot be empty")
    return normalized_platform


def _normalize_identity(platform: str, user_id: str) -> tuple[str, str]:
    normalized_platform = _normalize_platform(platform)
    normalized_user_id = user_id.strip()
    if not normalized_user_id:
        raise ValueError("user_id cannot be empty")
    return normalized_platform, normalized_user_id


def _normalize_language(language_code: str) -> str:
    normalized_language = language_code.strip()
    if not normalized_language:
        raise ValueError("language_code cannot be empty")
    return normalized_language


def _extract_identity(
    platform_or_bot: str | Bot,
    user_id_or_event: str | Event,
) -> tuple[str, str]:
    if isinstance(platform_or_bot, Bot) and isinstance(user_id_or_event, Event):
        return _normalize_identity(
            platform_or_bot.adapter.get_name(),
            user_id_or_event.get_user_id(),
        )

    if isinstance(platform_or_bot, str) and isinstance(user_id_or_event, str):
        return _normalize_identity(platform_or_bot, user_id_or_event)

    raise TypeError("expected (platform, user_id) or (bot, event)")


async def _get_binding(
    session: AsyncSession,
    platform: str,
    user_id: str,
) -> PlatformBinding | None:
    result = await session.execute(
        select(PlatformBinding).where(
            PlatformBinding.platform == platform,
            PlatformBinding.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def _get_account_platform_binding(
    session: AsyncSession,
    aid: int,
    platform: str,
) -> PlatformBinding | None:
    result = await session.execute(
        select(PlatformBinding).where(
            PlatformBinding.aid == aid,
            PlatformBinding.platform == platform,
        )
    )
    return result.scalar_one_or_none()


async def _create_account(
    session: AsyncSession,
    platform: str,
    language_code: str | None = None,
) -> UserAccount:
    account = UserAccount(
        language_code=language_code or plugin_config.locales_default_lang,
        primary_platform=platform,
    )
    session.add(account)
    await session.flush()
    return account


async def _create_binding(
    session: AsyncSession,
    platform: str,
    user_id: str,
    aid: int,
) -> PlatformBinding:
    binding = PlatformBinding(
        platform=platform,
        user_id=user_id,
        aid=aid,
        created_aid=aid,
    )
    session.add(binding)
    await session.flush()
    return binding


async def _create_identity(
    session: AsyncSession,
    platform: str,
    user_id: str,
    language_code: str | None = None,
) -> PlatformBinding:
    account = await _create_account(session, platform, language_code)
    return await _create_binding(session, platform, user_id, account.aid)


async def _get_or_create_binding(
    session: AsyncSession,
    platform: str,
    user_id: str,
    language_code: str | None = None,
) -> PlatformBinding:
    binding = await _get_binding(session, platform, user_id)
    if binding is not None:
        return binding
    return await _create_identity(session, platform, user_id, language_code)


async def _set_account_language(
    session: AsyncSession,
    aid: int,
    language_code: str,
) -> None:
    account = await session.get(UserAccount, aid)
    if account is None:
        raise AccountNotFoundError(f"aid {aid} does not exist")
    account.language_code = language_code


@overload
async def get_aid(
    platform: str,
    user_id: str,
    *,
    session: AsyncSession | None = None,
) -> int: ...


@overload
async def get_aid(
    bot: Bot,
    event: Event,
    *,
    session: AsyncSession | None = None,
) -> int: ...


async def get_aid(  # type: ignore[override]
    platform_or_bot: str | Bot,
    user_id_or_event: str | Event,
    *,
    session: AsyncSession | None = None,
) -> int:
    platform, user_id = _extract_identity(platform_or_bot, user_id_or_event)

    async with _session_scope(session) as (scoped_session, owns_session):
        try:
            binding = await _get_or_create_binding(scoped_session, platform, user_id)
            aid = binding.aid
            await _finalize(scoped_session, owns_session)
            return aid
        except IntegrityError:
            if not owns_session:
                raise

            await scoped_session.rollback()
            binding = await _get_binding(scoped_session, platform, user_id)
            if binding is None:
                raise
            return binding.aid


async def find_user_id(
    aid: int,
    platform: str,
    *,
    session: AsyncSession | None = None,
) -> str | None:
    normalized_platform = _normalize_platform(platform)

    async with _session_scope(session) as (scoped_session, _):
        result = await scoped_session.execute(
            select(PlatformBinding.user_id)
            .where(
                PlatformBinding.aid == aid,
                PlatformBinding.platform == normalized_platform,
            )
            .order_by(PlatformBinding.id)
            .limit(1)
        )
        return result.scalar_one_or_none()


async def get_user_id(
    aid: int,
    platform: str,
    *,
    session: AsyncSession | None = None,
) -> str:
    normalized_platform = _normalize_platform(platform)
    user_id = await find_user_id(aid, normalized_platform, session=session)
    if user_id is None:
        raise BindingNotFoundError(f"aid {aid} has no binding on {normalized_platform}")
    return user_id


async def get_bindings(
    aid: int,
    *,
    session: AsyncSession | None = None,
) -> dict[str, list[str]]:
    async with _session_scope(session) as (scoped_session, _):
        result = await scoped_session.execute(
            select(PlatformBinding.platform, PlatformBinding.user_id)
            .where(PlatformBinding.aid == aid)
            .order_by(PlatformBinding.platform, PlatformBinding.id)
        )
        bindings: dict[str, list[str]] = {}
        for platform, user_id in result.all():
            bindings.setdefault(platform, []).append(user_id)
        return bindings


async def get_bind_platform(
    aid: int,
    *,
    session: AsyncSession | None = None,
) -> set[str]:
    async with _session_scope(session) as (scoped_session, _):
        result = await scoped_session.execute(
            select(PlatformBinding.platform).where(PlatformBinding.aid == aid)
        )
        return set(result.scalars().all())


async def get_language(
    aid: int,
    *,
    session: AsyncSession | None = None,
) -> str:
    async with _session_scope(session) as (scoped_session, _):
        account = await scoped_session.get(UserAccount, aid)
        if account is None:
            raise AccountNotFoundError(f"aid {aid} does not exist")
        return account.language_code


async def set_language(
    platform: str,
    user_id: str,
    language_code: str,
    *,
    session: AsyncSession | None = None,
) -> None:
    normalized_platform, normalized_user_id = _normalize_identity(platform, user_id)
    normalized_language = _normalize_language(language_code)

    async with _session_scope(session) as (scoped_session, owns_session):
        binding = await _get_or_create_binding(
            scoped_session,
            normalized_platform,
            normalized_user_id,
            normalized_language,
        )
        await _set_account_language(scoped_session, binding.aid, normalized_language)
        if binding.created_aid != binding.aid:
            await _set_account_language(
                scoped_session,
                binding.created_aid,
                normalized_language,
            )
        await _finalize(scoped_session, owns_session)


async def bind_account(
    aid: int,
    platform: str,
    user_id: str,
    language_code: str,
    *,
    session: AsyncSession | None = None,
) -> int | None:
    normalized_platform, normalized_user_id = _normalize_identity(platform, user_id)
    normalized_language = _normalize_language(language_code)

    async with _session_scope(session) as (scoped_session, owns_session):
        target_account = await scoped_session.get(UserAccount, aid)
        if target_account is None:
            raise AccountNotFoundError(f"aid {aid} does not exist")

        binding = await _get_binding(
            scoped_session,
            normalized_platform,
            normalized_user_id,
        )
        existing_binding = await _get_account_platform_binding(
            scoped_session,
            aid,
            normalized_platform,
        )
        if existing_binding is not None and (
            binding is None or existing_binding.id != binding.id
        ):
            raise BindingConflictError(
                f"aid {aid} already has a binding on {normalized_platform}"
            )
        if binding is None:
            binding = await _create_identity(
                scoped_session,
                normalized_platform,
                normalized_user_id,
                normalized_language,
            )

        old_aid = binding.aid
        binding.aid = aid

        await _set_account_language(scoped_session, aid, normalized_language)
        if binding.created_aid != aid:
            await _set_account_language(
                scoped_session,
                binding.created_aid,
                normalized_language,
            )

        if old_aid != aid:
            scoped_session.add(
                AccountAuditLog(
                    operation="bind",
                    platform=normalized_platform,
                    user_id=normalized_user_id,
                    old_aid=old_aid,
                    new_aid=aid,
                )
            )
            await _finalize(scoped_session, owns_session)
            return old_aid

        await _finalize(scoped_session, owns_session)
        return None


async def unbind_account(
    platform: str,
    user_id: str,
    *,
    session: AsyncSession | None = None,
) -> int:
    normalized_platform, normalized_user_id = _normalize_identity(platform, user_id)

    async with _session_scope(session) as (scoped_session, owns_session):
        binding = await _get_or_create_binding(
            scoped_session,
            normalized_platform,
            normalized_user_id,
        )
        old_aid = binding.aid
        existing_binding = await _get_account_platform_binding(
            scoped_session,
            binding.created_aid,
            normalized_platform,
        )
        if existing_binding is not None and existing_binding.id != binding.id:
            raise BindingConflictError(
                f"aid {binding.created_aid} already has a binding on "
                f"{normalized_platform}"
            )
        binding.aid = binding.created_aid

        if old_aid != binding.created_aid:
            scoped_session.add(
                AccountAuditLog(
                    operation="unbind",
                    platform=normalized_platform,
                    user_id=normalized_user_id,
                    old_aid=old_aid,
                    new_aid=binding.created_aid,
                )
            )

        new_aid = binding.created_aid
        await _finalize(scoped_session, owns_session)
        return new_aid


__all__ = [
    "AccountNotFoundError",
    "BindingConflictError",
    "BindingNotFoundError",
    "LocalesAccountError",
    "bind_account",
    "find_user_id",
    "get_aid",
    "get_bind_platform",
    "get_bindings",
    "get_language",
    "get_user_id",
    "set_language",
    "unbind_account",
]
