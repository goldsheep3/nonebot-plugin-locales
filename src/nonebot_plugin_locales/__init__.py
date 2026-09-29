from nonebot import require
from nonebot.plugin import PluginMetadata

require("nonebot_plugin_localstore")
require("nonebot_plugin_datastore")
from .config import Config

__plugin_meta__ = PluginMetadata(
    name="跨平台语言和用户管理",
    description=(
        "跨适配器暴露可统一的 aid 并支持根据 aid 设置语言，"
        "插件可以手动编写 `assets/lang/zh_CN.yaml` 并使用 "
        '`await reply("register.success")` 实现语言自动适配'
    ),
    usage="await reply()",
    type="library",
    homepage="https://github.com/goldsheep3/nonebot-plugin-locales",
    config=Config,
    supported_adapters=None,
    extra={"author": "goldsheep3 gold_sheep_3@163.com"},
)


# --- export api ---

from . import matcher as matcher
from .api import (
    get_aid,
    get_user_id,
    find_user_id,
    get_bindings,
    get_language,
    get_bind_platform,
)
from .locales import Reply, locales_init

__all__ = [
    "Reply",
    "find_user_id",
    "get_aid",
    "get_bind_platform",
    "get_bindings",
    "get_language",
    "get_user_id",
    "locales_init",
]
