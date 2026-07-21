from collections.abc import AsyncIterator

import pytest
import nonebot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

nonebot.init()


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    from nonebot_plugin_locales.models import UserAccount

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(UserAccount.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    await engine.dispose()
