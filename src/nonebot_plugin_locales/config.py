from nonebot import get_driver, get_plugin_config
from pydantic import BaseModel


class Config(BaseModel):
    # 默认语言
    DEFAULT_LANG: str = "en_US"


# 配置加载
plugin_config: Config = get_plugin_config(Config)
