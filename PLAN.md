# NoneBot2 跨平台用户绑定与本地化插件设计方案

## 1. 项目概述

本插件旨在为 NoneBot2 生态提供一个轻量级、高内聚的跨平台用户身份统一模块。核心功能包括：
- **统一身份标识 (AID)**：将不同聊天平台（如 QQ、Telegram、Discord）的用户 ID 映射至全局唯一的 AID。
- **声明式本地化 (i18n)**：提供基于 YAML 和依赖注入的多语言文本渲染引擎。
- **标准化指令集**：内置账号绑定与解绑的 Matcher，支持正则表达式路由。

## 2. 目录结构设计

采用高内聚、低耦合的模块化目录结构，确保业务逻辑与框架层解耦。

```text
nonebot_plugin_account/
├── __init__.py          # 插件入口，导出 API 与注册 Matcher
├── models.py            # 数据库模型 (SQLAlchemy 2.0 声明式映射)
├── api.py               # 核心业务逻辑与对外暴露的 API
├── locales.py           # 本地化引擎与依赖注入工厂
├── matchers.py          # 独立 Matcher 定义与指令处理
├── config.py            # 插件配置项 (基于 pydantic)
└── assets/
    └── lang/            # 多语言资源目录
        ├── zh_CN.yaml
        └── en_US.yaml
```

## 3. 数据库设计 (Datastore 集成)

基于 `nonebot-plugin-datastore` 提供的异步 SQLAlchemy 会话，采用 2.0 风格的声明式映射（Declarative Mapping）。

### 3.1 实体关系 (ER) 模型

| 表名 (实体) | 核心职责 | 关键约束 |
| :--- | :--- | :--- |
| `UserAccount` | 存储全局用户主档案与偏好设置 | 主键 `aid` 自增 |
| `PlatformBinding` | 存储具体平台与 AID 的映射关系 | 联合唯一约束 `(platform, user_id)` |
| `AccountAuditLog` | 审计日志，记录 AID 的变更与转移历史 | 外键关联 `UserAccount.aid` |

### 3.2 模型定义实现

```python
# models.py
from datetime import datetime
from nonebot_plugin_datastore import get_plugin_data
from sqlalchemy import UniqueConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

Model = get_plugin_data().Model

class UserAccount(Model):
    __table_name__ = "locales_user_account"

    aid: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="account_id")
    language_code: Mapped[str] = mapped_column(nullable=False, default="zh_CN")
    primary_platform: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, nullable=False)

class PlatformBinding(Model):
    __table_name__ = "locales_platform_binding"
    __table_args__ = (
        UniqueConstraint("platform", "user_id", name="uq_platform_user"),
    )
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(nullable=False)
    aid: Mapped[int] = mapped_column(ForeignKey("locales_user_account.aid"), nullable=False, index=True)
    created_aid: Mapped[int] = mapped_column(ForeignKey("locales_user_account.aid"), nullable=False, index=True)

class AccountAuditLog(Model):
    __table_name__ = "locales_account_audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(nullable=False)
    user_id: Mapped[str] = mapped_column(nullable=False)
    old_aid: Mapped[int] = mapped_column(ForeignKey("locales_user_account.aid"), nullable=False)
    new_aid: Mapped[int] = mapped_column(ForeignKey("locales_user_account.aid"), nullable=False)
    operationed_at: Mapped[datetime] = mapped_column(default=datetime.now, nullable=False)
```

## 4. 核心 API 设计

对外暴露的 API 需保证类型安全与异步非阻塞特性。针对 `get_aid` 的多态需求，采用 `typing.overload` 结合运行时类型收窄（Type Narrowing）实现。

### 4.1 接口契约

| 函数签名 | 参数说明 | 返回值 | 异常/边界处理 |
| :--- | :--- | :--- | :--- |
| `get_aid(platform, user_id)` | 平台标识, 平台用户ID | `int` (AID) | 若不存在则自动创建档案并返回新 AID |
| `get_aid(bot, event)` | NoneBot Bot 实例, Event 实例 | `int` (AID) | 自动从适配器提取 platform 和 user_id |
| `get_user_id(aid, platform)` | AID, 平台标识 | `str` (User ID) | 若未绑定则抛出 `ValueError` |
| `get_bind_platform(aid)` | AID | `set[str]` | 返回空集合表示未绑定任何平台 |

### 4.2 多态实现机制

```python
# api.py (节选)
from typing import overload, Union
from nonebot.adapters import Bot, Event

@overload
async def get_aid(platform: str, user_id: str) -> int: ...

@overload
async def get_aid(bot: Bot, event: Event) -> int: ...

async def get_aid(
    platform_or_bot: Union[str, Bot], 
    user_id_or_event: Union[str, Event]
) -> int:
    if isinstance(platform_or_bot, Bot) and isinstance(user_id_or_event, Event):
        platform = platform_or_bot.adapter.get_name().lower()
        user_id = user_id_or_event.get_user_id()
    else:
        platform = str(platform_or_bot)
        user_id = str(user_id_or_event)

    # 后续执行数据库查询与 Upsert 逻辑...
```

## 5. 本地化 (i18n) 与依赖注入设计

为支持其他插件无缝接入本插件的本地化引擎，采用**工厂模式**结合 NoneBot2 的 `Depends` 机制。

### 5.1 架构工作流

1. **初始化阶段**：调用 `locales_init(Path)` 读取并缓存 YAML 文件至内存，返回依赖工厂 `Reply`。
2. **注入阶段**：在 Matcher 中通过 `reply = Reply` 触发依赖注入，生成当前请求上下文的 `reply` 闭包。
3. **渲染阶段**：调用 `await reply("key", **kwargs)` 执行安全的字符串格式化。

### 5.2 资源文件规范

```yaml
# assets/lang/zh_CN.yaml
bind:
  success: "绑定成功！您的全局 AID 为 {aid}，目标参数：{target}"
  fail: "绑定失败：{reason}"
unbind:
  confirm: "确认要解绑 {target} 吗？"
```

### 5.3 引擎实现

```python
# locales.py
import yaml
from pathlib import Path
from nonebot.params import Depends

def locales_init(lang_dir: Path):
    lang_data: dict[str, dict] = {}
    if lang_dir.exists():
        for file in lang_dir.glob("*.yaml"):
            with open(file, "r", encoding="utf-8") as f:
                lang_data[file.stem] = yaml.safe_load(f) or {}

    def _dependency():
        async def reply(key: str, **kwargs) -> str:
            current_lang = "zh_CN" # 实际应用中可从 UserAccount.lang 动态获取
            data = lang_data.get(current_lang, {})
            
            for k in key.split("."):
                if isinstance(data, dict):
                    data = data.get(k)
                else:
                    return key
                    
            if isinstance(data, str):
                try:
                    return data.format_map(kwargs)
                except KeyError:
                    return data
            return key

        return reply

    return Depends(_dependency)
```

## 6. Matcher 与指令路由设计

指令处理层仅负责参数解析与响应分发，核心业务逻辑全部委托给 `api.py`。

### 6.1 路由定义

| 指令模式 | 正则表达式 | 优先级 | 阻断 (Block) | 职责 |
| :--- | :--- | :--- | :--- | :--- |
| `/lang` | `^/lang\s+(?P<lang>\S+)?$` | 10 | True | 处理语言绑定 |
| `/bind` | `^/bind\s+(?P<arg>\S+)$` | 10 | True | 处理跨平台账号绑定请求 |
| `/unbind` | `^/unbind\s+(?P<arg>\S+)$` | 10 | True | 处理账号解绑与日志记录 |

### 6.2 处理器实现

```python
# matchers.py
from pathlib import Path
from nonebot import on_regex
from nonebot.adapters import Bot, Event
from nonebot.params import RegexDict

from .api import get_aid
from .locales import locales_init

_lang_dir = Path(__file__).parent / "assets" / "lang"
Reply = locales_init(_lang_dir)

lang_setting_matcher = on_regex(r"^/lang\s+(?P<lang>\S+)?$", priority=10, block=True)
bind_matcher = on_regex(r"^/bind\s+(?P<arg>\S+)$", priority=10, block=True)
unbind_matcher = on_gegex(r"^/unbind\s+(?P<arg>\S+)$", priority=10, block=True)

@bind_matcher.handle()
async def bind_handled(
    bot: Bot, 
    event: Event, 
    args: dict = RegexDict(), 
    reply = Reply
):
    arg = args.get("arg", "")
    aid = await get_aid(bot, event)
    
    result = await reply("bind.success", aid=aid, target=arg)
    await bind_matcher.finish(result)
```

## 7. 第三方插件集成指南

其他插件开发者可通过以下标准范式引入本插件的能力：

```python
from nonebot import require
from pathlib import Path

# 1. 确保插件已加载
require("nonebot_plugin_account")
from nonebot_plugin_account import get_aid, locales_init

# 2. 初始化本插件的本地化资源
_my_lang_dir = Path(__file__).parent / "lang"
_Reply = locales_init(_my_lang_dir)

# 3. 在 Matcher 中使用
from nonebot import on_command
from nonebot.adapters import Bot, Event

test_matcher = on_command("test")

@test_matcher.handle()
async def _(bot: Bot, event: Event, reply=_Reply):
    # 获取 aid 作为用户 id 主键
    user_aid = await get_aid(bot, event)
    
    # 使用 i18n 获取文本
    msg = await reply("test.greeting")
    await test_matcher.finish(msg)
```
