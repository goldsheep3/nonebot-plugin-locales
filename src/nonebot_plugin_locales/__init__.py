from nonebot import require
from nonebot.plugin import PluginMetadata

require("nonebot_plugin_localstore")
require("nonebot_plugin_datastore")
from .config import Config

__plugin_meta__ = PluginMetadata(  # type: ignore
    name="跨平台语言和用户管理",
    description=(
        "跨适配器暴露可统一的 aid 并支持根据 aid 设置语言，"
        "插件可以手动编写 `assets/locales/zh_CN.yaml` 并使用 "
        '`reply("register.success")` 实现语言自动适配'
    ),
    usage="reply()",
    type="library",
    homepage="https://github.com/goldsheep3/nonebot-plugin-locales",
    config=Config,
    supported_adapters=None,
    extra={"author": "goldsheep3 gold_sheep_3@163.com"},
)


# --- export api ---

from . import matcher as matcher
from .api import (
    BIND_TOKEN_TTL,
    BindingTokenClaim,
    BindingTokenCreateError,
    LocalesAccountError,
    AccountNotFoundError,
    BindingConflictError,
    BindingNotFoundError,
    get_aid,
    get_user_id,
    bind_account,
    find_user_id,
    get_bindings,
    get_language,
    set_language,
    unbind_account,
    get_bind_platform,
    claim_binding_token,
    create_binding_token,
    normalize_language_code,
)
from .locales import Reply, LocaleError, LocaleStore, LocaleFileError, locales_init

__all__ = [
    "BIND_TOKEN_TTL",
    "AccountNotFoundError",
    "BindingConflictError",
    "BindingNotFoundError",
    "BindingTokenClaim",
    "BindingTokenCreateError",
    "LocaleError",
    "LocaleFileError",
    "LocaleStore",
    "LocalesAccountError",
    "Reply",
    "bind_account",
    "claim_binding_token",
    "create_binding_token",
    "find_user_id",
    "get_aid",
    "get_bind_platform",
    "get_bindings",
    "get_language",
    "get_user_id",
    "locales_init",
    "matcher",
    "normalize_language_code",
    "set_language",
    "unbind_account",
]
