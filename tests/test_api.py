import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from nonebot_plugin_locales.api import (
    BindingConflictError,
    get_aid,
    get_user_id,
    bind_account,
    find_user_id,
    get_bindings,
    get_language,
    set_language,
    unbind_account,
    get_bind_platform,
)
from nonebot_plugin_locales.models import (
    UserAccount,
    AccountAuditLog,
    PlatformBinding,
)


def test_normalize_language_code_accepts_common_spellings() -> None:
    from nonebot_plugin_locales.api import normalize_language_code

    assert normalize_language_code(" en-us ") == "en_US"
    assert normalize_language_code("ZH_cn") == "zh_CN"
    assert normalize_language_code("ja") == "ja"


def test_extract_identity_rejects_mixed_argument_types() -> None:
    from nonebot_plugin_locales.api import _extract_identity

    with pytest.raises(TypeError, match="expected"):
        _extract_identity("onebot", 123)  # type: ignore[arg-type]


async def test_get_aid_creates_account_and_origin_binding(
    db_session: AsyncSession,
) -> None:
    aid = await get_aid("OneBot", " 123 ", session=db_session)

    account = await db_session.get(UserAccount, aid)
    binding = await db_session.scalar(select(PlatformBinding))

    assert account is not None
    assert account.primary_platform == "onebot"
    assert account.language_code == "zh_CN"
    assert binding is not None
    assert binding.platform == "onebot"
    assert binding.user_id == "123"
    assert binding.aid == aid
    assert binding.created_aid == aid


async def test_bind_account_records_log_and_unbind_restores_origin(
    db_session: AsyncSession,
) -> None:
    owner_aid = await get_aid("onebot", "owner", session=db_session)
    member_origin_aid = await get_aid("telegram", "member", session=db_session)

    old_aid = await bind_account(
        owner_aid,
        "Telegram",
        "member",
        "en_US",
        session=db_session,
    )
    binding = await db_session.scalar(
        select(PlatformBinding).where(PlatformBinding.user_id == "member")
    )

    assert old_aid == member_origin_aid
    assert binding is not None
    assert binding.aid == owner_aid
    assert binding.created_aid == member_origin_aid
    assert await get_bind_platform(owner_aid, session=db_session) == {
        "onebot",
        "telegram",
    }
    assert await get_bindings(owner_aid, session=db_session) == {
        "onebot": ["owner"],
        "telegram": ["member"],
    }

    restored_aid = await unbind_account("telegram", "member", session=db_session)

    assert restored_aid == member_origin_aid
    assert binding.aid == member_origin_aid
    logs = (
        await db_session.scalars(select(AccountAuditLog).order_by(AccountAuditLog.id))
    ).all()
    assert [log.operation for log in logs] == ["bind", "unbind"]
    assert [(log.old_aid, log.new_aid) for log in logs] == [
        (member_origin_aid, owner_aid),
        (owner_aid, member_origin_aid),
    ]


async def test_bind_account_rejects_second_identity_on_same_platform(
    db_session: AsyncSession,
) -> None:
    owner_aid = await get_aid("onebot", "owner", session=db_session)
    first_origin_aid = await get_aid("telegram", "first", session=db_session)
    second_origin_aid = await get_aid("telegram", "second", session=db_session)
    await bind_account(
        owner_aid,
        "telegram",
        "first",
        "zh_CN",
        session=db_session,
    )

    with pytest.raises(BindingConflictError):
        await bind_account(
            owner_aid,
            "telegram",
            "second",
            "en_US",
            session=db_session,
        )

    assert await find_user_id(owner_aid, "telegram", session=db_session) == "first"
    assert await get_aid("telegram", "second", session=db_session) == second_origin_aid
    assert await get_language(owner_aid, session=db_session) == "zh_CN"
    assert await get_language(second_origin_aid, session=db_session) == "zh_CN"
    assert first_origin_aid != second_origin_aid


async def test_database_rejects_duplicate_aid_platform(
    db_session: AsyncSession,
) -> None:
    aid = await get_aid("onebot", "owner", session=db_session)
    db_session.add(
        PlatformBinding(
            platform="onebot",
            user_id="other",
            aid=aid,
            created_aid=aid,
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_set_language_updates_current_and_created_accounts(
    db_session: AsyncSession,
) -> None:
    owner_aid = await get_aid("onebot", "owner", session=db_session)
    member_origin_aid = await get_aid("telegram", "member", session=db_session)
    await bind_account(
        owner_aid,
        "telegram",
        "member",
        "en_US",
        session=db_session,
    )

    await set_language("telegram", "member", "ja_JP", session=db_session)

    assert await get_language(owner_aid, session=db_session) == "ja_JP"
    assert await get_language(member_origin_aid, session=db_session) == "ja_JP"


async def test_query_helpers_return_empty_results_for_unknown_aid(
    db_session: AsyncSession,
) -> None:
    assert await get_bindings(999, session=db_session) == {}
    assert await get_bind_platform(999, session=db_session) == set()


async def test_find_user_id_returns_none_for_unbound_platform(
    db_session: AsyncSession,
) -> None:
    aid = await get_aid("onebot", "owner", session=db_session)

    assert await find_user_id(aid, "telegram", session=db_session) is None


async def test_find_user_id_returns_bound_identity(
    db_session: AsyncSession,
) -> None:
    aid = await get_aid("onebot", "owner", session=db_session)
    await bind_account(aid, "telegram", "member", "zh_CN", session=db_session)

    assert await find_user_id(aid, "Telegram", session=db_session) == "member"


async def test_get_aid_is_idempotent(db_session: AsyncSession) -> None:
    first_aid = await get_aid(" OneBot ", " user ", session=db_session)
    second_aid = await get_aid("onebot", "user", session=db_session)

    assert second_aid == first_aid
    assert len((await db_session.scalars(select(UserAccount))).all()) == 1
    assert len((await db_session.scalars(select(PlatformBinding))).all()) == 1


async def test_bind_account_is_idempotent_for_same_binding(
    db_session: AsyncSession,
) -> None:
    aid = await get_aid("onebot", "owner", session=db_session)

    assert (
        await bind_account(aid, "onebot", "owner", "en_US", session=db_session) is None
    )
    assert await get_language(aid, session=db_session) == "en_US"
    assert (await db_session.scalars(select(AccountAuditLog))).all() == []


async def test_get_user_id_returns_bound_identity(
    db_session: AsyncSession,
) -> None:
    aid = await get_aid("onebot", "owner", session=db_session)

    assert await get_user_id(aid, " ONEBOT ", session=db_session) == "owner"


async def test_get_user_id_raises_for_missing_binding(
    db_session: AsyncSession,
) -> None:
    from nonebot_plugin_locales.api import BindingNotFoundError, get_user_id

    with pytest.raises(BindingNotFoundError, match="has no binding"):
        await get_user_id(999, "telegram", session=db_session)


async def test_public_api_validates_empty_values(db_session: AsyncSession) -> None:
    with pytest.raises(ValueError, match="platform cannot be empty"):
        await get_aid(" ", "user", session=db_session)
    with pytest.raises(ValueError, match="user_id cannot be empty"):
        await get_aid("onebot", " ", session=db_session)
    with pytest.raises(ValueError, match="language_code cannot be empty"):
        await set_language("onebot", "user", " ", session=db_session)


async def test_session_is_rolled_back_after_api_error(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(ValueError, match="user_id cannot be empty"):
        await get_aid("onebot", " ", session=db_session)

    aid = await get_aid("onebot", "usable-after-error", session=db_session)
    assert aid > 0


async def test_public_api_raises_for_missing_account(
    db_session: AsyncSession,
) -> None:
    from nonebot_plugin_locales.api import AccountNotFoundError

    with pytest.raises(AccountNotFoundError, match="does not exist"):
        await get_language(999, session=db_session)
    with pytest.raises(AccountNotFoundError, match="does not exist"):
        await bind_account(999, "onebot", "user", "zh_CN", session=db_session)


async def test_unbind_account_creates_missing_identity(
    db_session: AsyncSession,
) -> None:
    aid = await unbind_account("onebot", "new-user", session=db_session)
    binding = await db_session.scalar(select(PlatformBinding))

    assert binding is not None
    assert binding.aid == aid
    assert binding.created_aid == aid
    assert await get_language(aid, session=db_session) == "zh_CN"
