from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nonebot_plugin_locales.api import (
    get_aid,
    bind_account,
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


async def test_unbind_account_creates_missing_identity(
    db_session: AsyncSession,
) -> None:
    aid = await unbind_account("onebot", "new-user", session=db_session)
    binding = await db_session.scalar(select(PlatformBinding))

    assert binding is not None
    assert binding.aid == aid
    assert binding.created_aid == aid
    assert await get_language(aid, session=db_session) == "zh_CN"
