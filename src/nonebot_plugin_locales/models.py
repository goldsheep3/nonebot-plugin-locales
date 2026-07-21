from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from nonebot_plugin_datastore import get_plugin_data

Model = get_plugin_data("nonebot_plugin_locales").Model


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserAccount(Model):
    __tablename__ = "locales_user_account"

    aid: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="Global account id")
    language_code: Mapped[str] = mapped_column(String(32), nullable=False, default="zh_CN", comment="Preferred locale code")
    primary_platform: Mapped[str] = mapped_column(String(64), nullable=False, comment="Platform that created this account")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class PlatformBinding(Model):
    __tablename__ = "locales_platform_binding"
    __table_args__ = (
        UniqueConstraint("platform", "user_id", name="uq_locales_platform_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(191), nullable=False)
    aid: Mapped[int] = mapped_column(Integer, ForeignKey("locales_user_account.aid"), nullable=False, index=True,)
    created_aid: Mapped[int] = mapped_column(Integer, ForeignKey("locales_user_account.aid"), nullable=False, index=True,)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class AccountAuditLog(Model):
    __tablename__ = "locales_account_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    operation: Mapped[str] = mapped_column(String(32), nullable=False)
    platform: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(191), nullable=False)
    old_aid: Mapped[int] = mapped_column(Integer, ForeignKey("locales_user_account.aid"), nullable=False)
    new_aid: Mapped[int] = mapped_column(Integer, ForeignKey("locales_user_account.aid"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


__all__ = [
    "AccountAuditLog",
    "PlatformBinding",
    "UserAccount",
]
