# nonebot-plugin-locales

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> 为 [NoneBot2](https://github.com/nonebot/nonebot2) 提供跨平台身份统一（AID）与本地化（i18n）能力的插件。

## 简介

`nonebot-plugin-locales` 通过稳定的全局 AID（Account ID）将不同聊天平台上的用户身份归并到同一账号下，并为每个 AID 保存语言偏好，从而让其他插件能够以统一、可注入的方式向用户返回本地化文本。

## 特性

- 🌐 **全局 AID 管理**：为 `(platform, user_id)` 创建并查询稳定的全局 AID
- 🔗 **跨平台身份合并**：通过一次性绑定令牌，将不同平台的身份合并至同一 AID
- 🔒 **唯一绑定约束**：一个 AID 在同一平台只能绑定一个身份，避免歧义
- 📝 **操作审计**：记录绑定、解绑操作
- 🗣️ **语言偏好**：为每个 AID 保存语言偏好，并支持 YAML 本地化资源
- 🧩 **可注入的 `reply()`**：为其他插件提供可注入的异步 `reply()` 本地化函数
- 🛡️ **安全令牌**：令牌仅保存摘要、十分钟有效、使用后立即失效，并可在多个 Bot 实例间共享

## 环境要求

- Python >= 3.10（建议 3.12）
- NoneBot2 >= 2.5
- [nonebot-plugin-datastore](https://github.com/he0119/nonebot-plugin-datastore)：用于存储 AID、绑定关系等信息

## 安装

本插件尚未发布到 PyPI，请通过 Git 仓库安装：

```bash
uv add "git+https://github.com/goldsheep3/nonebot-plugin-locales.git@v0.1.0"
```

或使用 pip：

```bash
pip install "git+https://github.com/goldsheep3/nonebot-plugin-locales.git@v0.1.0"
```

## 配置

在 `.env` 中可配置以下项：

| 配置项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `LOCALES_DEFAULT_LANG` | `str` | `zh_CN` | 默认语言，当 AID 未设置语言偏好时使用 |

## 用户指令

| 指令 | 别名 | 说明 |
| --- | --- | --- |
| `/bind` | `/绑定` | 在当前平台生成一次性绑定令牌 |
| `/bind <token>` | `/绑定 <token>` | 在目标平台使用令牌完成绑定 |
| `/bind help` | `/bind 帮助` | 查看绑定帮助 |
| `/unbind` | `/解绑` | 解绑当前平台身份，恢复其初始 AID |
| `/unbind <platform>` | `/解绑 <platform>` | 解绑当前 AID 中指定平台的身份 |
| `/lang` | `/language`、`/语言`、`/设置语言` | 查看当前语言 |
| `/lang <language>` | 同上 | 设置当前语言，例如 `/lang en_US` |
| `/lang help` | `/lang 帮助` | 查看可用语言 |

### 快速绑定流程

1. 在主平台向 Bot 发送 `/bind`；
2. Bot 返回一条完整的 `/bind <token>` 指令；
3. 在目标平台、目标账号对应的 Bot 上发送这条指令；
4. 目标身份会归入主平台账号的 AID。未来如果解绑，目标账号将会还原到原先的 AID。

> 令牌仅保存摘要、十分钟内有效、使用后立即失效。

## 开发者文档

### 编辑语言资源

语言资源为 YAML 文件，文件名严格为 `xx_XX`（如 `zh_CN.yaml`、`en_US.yaml`）：

```
assets/lang/
├── zh_CN.yaml
├── en_US.yaml
└── xx_XX.yaml
```

```yaml
# zh_CN.yaml
hello: "你好，{name}！"
```

```yaml
# en_US.yaml
hello: "Hello, {name}!"
```

资源中支持 `{name}` 形式的占位符，通过 `reply(key, **kwargs)` 传入；键支持 `.` 分隔的嵌套写法。节点也可使用仅由字符串构成的列表，`reply()` 会随机选择其中一条并进行格式化：

```yaml
greeting:
  - "你好，{name}！"
  - "欢迎回来，{name}！"
```

### 快速使用

至少先 require 一次，加载 `nonebot-plugin-locales`：

```python
from nonebot import require
require("nonebot_plugin_locales")
```

加载后，需要进行预获取：

```python
_LANG_DIR = Path(...)  # 通常为插件根目录下 `assets/lang` 文件夹
Reply = locales_init(_LANG_DIR)
```

随后，可以复用该 Reply 对象，使用 reply 函数：

```python
@matcher1.handle()
async def matcher1_handle(..., reply=Reply):
    ...

@matcher2.handle()
async def matcher2_handle(..., reply=Reply):
    ...
```

#### _def_ `locales_init(lang_dir)`

- **说明:** 获取用于注入的 `Reply` 对象。

- **参数**
  - `lang_dir` (str | Path): 多语言支持文件存储位置。通常为插件根目录下 `assets/lang` 文件夹。

- **返回**
  - Callable[..., Awaitable[str]]: 用于注入的 `Reply` 对象。

- **用法**

  ```python
  @matcher.handle()
  async def matcher_handle(..., reply=Reply):
      ...
  ```

#### _Callable_ `Reply(key, **kwargs)`

- **说明:** 获取语言文本。

- **参数**
  - `key` (str): yaml 中编写的，以点号 `.` 为分隔的多语言 key。
  - **kwargs: 用于替换语言文本中的`{xxx}`部分。

- **返回**
- Awaitable[str]: 异步返回替换参数后的对应语言文本（或在不存在该语言文件时的回退语言文本）。如果对应文件中不存在对应的 key，会返回原键名 key。

- **用法**

  ```python
  # 假定 `register.success.common: "{user_id} Register Success."`
  @matcher1.handle()
  async def matcher1_handle(..., reply=Reply):
      message = await reply("register.success.common", user_id="123456")
      # "123456 Register Success."

  # 假定下述键不存在
  @matcher2.handle()
  async def matcher2_handle(..., reply=Reply):
      message = await reply("register.success.special", user_id="123456")
      # "register.success.special"
  ```

### 可调用的函数

**函数可以自主传入 `session=AsyncSession`。该种情况下，需要自行处理 `IntegrityError` 错误。**

#### _async def_ `get_aid(platform_or_bot, user_id_or_event)`

- **说明:** 获取指定用户的 AID。

- **重载**

  **1.** `async (platform_or_bot: str, user_id_or_event: str) -> int`
  - **参数**
    - `platform_or_bot` (str): 平台名称。
    - `user_id_or_event` (str): 该用户在该平台的用户 ID。

  - **返回**
    - int: 该用户的 AID。

  **2.** `async (platform_or_bot: Bot, user_id_or_event: Event) -> int`
  - **参数**
    - `platform_or_bot` (Bot): nonebot 提供的 Bot。
    - `user_id_or_event` (Event): nonebot 提供的 Event。

  - **返回**
    - int: 该用户的 AID。

- **用法**

  ```python
  from nonebot_plugin_locales import get_aid

  # 显式指定平台与用户 ID
  aid = await get_aid("onebot", "123456")

  # 在 Matcher 中直接从当前事件解析
  aid = await get_aid(bot, event)
  ```


#### _async def_ `get_user_id(aid, platform)`

- **说明:** 查询某个 AID 在指定平台上绑定的用户 ID。

- **参数**
  - `aid` (int): 该用户的 AID。
  - `platform` (str): 指定的平台。

- **返回**
  - str: 该用户的 `user_id`。

- **异常**
  - `BindingNotFoundError`: 该用户未绑定该平台账号。

- **用法**

  ```python
  from nonebot_plugin_locales import get_user_id

  user_id = await get_user_id(aid, "onebot")
  ```


#### _async def_ `find_user_id(aid, platform)`

- **说明:** 查询某个 AID 在指定平台上绑定的用户 ID，未绑定时返回 `None` 而不抛出异常。

- **参数**
  - `aid` (int): 该用户的 AID。
  - `platform` (str): 指定的平台。

- **返回**
  - str | None: 若该用户已绑定该平台账号，返回其对应的 `user_id`；否则返回 `None`。

- **用法**

  ```python
  from nonebot_plugin_locales import find_user_id

  # 若未绑定，返回 None
  user_id = await find_user_id(aid, "onebot")
  ```


#### _async def_ `get_bindings(aid)`

- **说明:** 获取某个 AID 绑定的全部平台账号，按平台分组返回。

- **参数**
  - `aid` (int): 该用户的 AID。

- **返回**
  - dict[str, str]: 以平台名称为键、该平台下绑定的 `user_id` 为值的字典。

- **用法**

  ```python
  from nonebot_plugin_locales import get_bindings

  bindings = await get_bindings(aid)
  # {"onebot": "789012", "discord": "345678"}
  ```


#### _async def_ `get_bind_platform(aid)`

- **说明:** 获取某个 AID 已绑定的全部平台名称。

- **参数**
  - `aid` (int): 该用户的 AID。

- **返回**
  - set[str]: 该用户已绑定的平台名称集合；若未绑定任何平台，返回空集合。

- **用法**

  ```python
  from nonebot_plugin_locales import get_bind_platform

  platforms = await get_bind_platform(aid)
  # {"onebot", "discord"}
  ```

#### _async def_ `get_language(aid)`

- **说明:** 获取指定 AID 的账号语言代码。

- **参数**
  - `aid` (int): 该用户的 AID。

- **返回**
  - str: 该账号的语言代码。

- **异常**
  - `AccountNotFoundError`: 该 AID 不存在。

- **用法**

  ```python
  from nonebot_plugin_locales import get_language

  language_code = await get_language(aid)
  # "zh_CN"
  ```

## 许可证

本项目基于 [MIT](https://opensource.org/licenses/MIT) 许可证开源。
