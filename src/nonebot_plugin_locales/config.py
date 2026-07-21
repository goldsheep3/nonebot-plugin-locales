from nonebot import get_plugin_config
from pydantic import BaseModel


class Config(BaseModel):
    # 默认语言
    locales_default_lang: str = "zh_CN"


# 配置加载
plugin_config: Config = get_plugin_config(Config)
