# 开发说明

面向维护/扩展 EPbot 的开发者。面向使用者的说明见 [README.md](./README.md)。

## 环境与依赖

- Python 3.8+
- [khl.py](https://github.com/TWT233/khl.py)

```bash
pip install -r requirements.txt
```

`requirements.txt` 只有一行 `-e .`（把本项目装上），依赖声明的唯一来源是 `pyproject.toml` 里的
`khl.py~=0.3.17`（可用版本 `>= 0.3.17, < 0.4`，用 `~=` 挡住 0.4 的破坏性改动）：
`aiohttp` / `pycryptodomex` / `apscheduler` 都由它自动带入，不手写以免和 SDK 声明的版本打架。

装包时会按 `[project.scripts]` 生成 `epbot` 控制台命令（指向 `epbot.main:run`），
所以 `epbot` 与 `python -m epbot` 等价。项目自带的 `venv/` 实测 **Python 3.14.7** 可以正常运行。

## 项目结构

采用 src 布局：代码在 `src/epbot/`，运行时可写数据在 `data/`，两者分开。

```text
KOOK_EPbot-1.0/
├── README.md            # 使用说明（面向使用者）
├── DEVELOPER.md         # 开发说明（本文件）
├── pyproject.toml       # 包元数据 + 依赖声明（唯一来源）
├── requirements.txt     # 只有一行 -e .
├── .gitignore
├── venv/                # 本地虚拟环境（体积大，不要提交）
├── data/                # 运行时可写数据（不在包里）
│   ├── welcome_channels.json  # 欢迎开关 {guild_id: channel_id}
│   └── ticket_state.json      # 面板频道与工单归属
└── src/
    └── epbot/
        ├── __init__.py   # 包说明 + __version__（版本号唯一来源）
        ├── __main__.py   # python -m epbot 入口
        ├── paths.py      # 路径解析：配置位置、数据目录
        ├── config.py     # 配置加载：TOKEN / CACHE_TTL / ADMIN_PERMISSION_BIT
        ├── config.example.json  # 配置模板（无 Token），首次使用复制成 config.json
        ├── bot.py        # Bot 单例
        ├── common.py     # 共用工具：read_json / write_json_atomic / is_channel_gone / channel_alive
        ├── admin.py      # 管理员校验与 TTL 缓存
        ├── commands.py   # admin_rule / 异常处理 / COMMAND_USAGE / ADMIN_ONLY
        ├── main.py       # register() 注册 + run() 启动
        ├── welcome/
        │   ├── __init__.py
        │   └── welcome.py          # /welcome 指令 + 入服事件
        └── ticket/
            ├── __init__.py
            ├── ticket_config.json  # 按钮名字与 value 暗号、频道前缀等（跟代码走）
            ├── ticket_cards.py     # 只生成卡片：get_menu_card() / get_ticket_card(content)
            └── ticket_manager.py   # 业务：/ticket 指令、按钮点击、建私密频道、关票
```

几个刻意的安排：

- **代码与运行数据分离**：包目录里只有代码和「跟着代码走的配置」（`ticket_config.json`），
  状态文件和 `config.json` 都不在包内；`config.json` 故意不打包（含 Token），由部署方自己提供 ——
  仓库里给了 `config.example.json` 模板（它会被打进 wheel），复制成 `config.json` 即可。
  配置缺失时 `config.py` 会把「复制模板」的命令和 `KOOK_TOKEN` 两条路都打印出来。
- **`paths.py` 是唯一拼路径的地方**，其他模块一律 `from ..paths import ...`；
  配置位置与数据目录可用 `EPBOT_CONFIG` / `EPBOT_DATA_DIR` 覆盖（生产环境可把可写数据挪出代码目录）。
- **导入无副作用**：`import epbot.main` 不会注册任何指令，必须显式调 `register()`
  （khl.py 的 CommandManager 遇到同名指令会直接报错，只应注册一次）。
- **`bot.py` 单独存在**是为了让 `admin` / `commands` / 功能模块都能拿到同一个 Bot 实例，
  而不用反向 import `main`（那会形成循环依赖）。

启动：仓库根目录下 `python -m epbot`（或装包后生成的 `epbot` 命令）。

## 模块职责

| 模块 | 内容 |
| --- | --- |
| `paths.py` | `PACKAGE_DIR` / `PROJECT_ROOT` / `CONFIG_PATH` / `DATA_DIR` 及三个文件路径、`ensure_data_dir()` |
| `config.py` | 读取 `config.json`，导出 `TOKEN_ENV` / `TOKEN`（环境变量优先）、`ADMIN_PERMISSION_BIT`、`CACHE_TTL` |
| `bot.py` | 全局 `bot` 单例 |
| `common.py` | `read_json` / `write_json_atomic` / `is_channel_gone` / `channel_alive` / `TTLCache` |
| `admin.py` | 三个 `TTLCache`（软/硬两层 TTL）；`is_admin` / `is_guild_admin` / `admin_only` |
| `commands.py` | `admin_rule`（规则）、`on_rule_not_passed` / `on_arg_len_not_matched`（异常处理）、`COMMAND_USAGE`、`ADMIN_ONLY` |
| `main.py` | `register()` 注册 `/help` 与两个功能模块；`run()` 启动 |

## 管理员判定逻辑

`is_admin(msg)` 按顺序判断，返回 `True` 即通过：

1. `msg.ctx.guild` 为空（私聊）→ `False`
2. `msg.author_id == guild.master_id` → 服主，`True`
3. 该成员的角色中，存在 `role.has_permission(ADMIN_PERMISSION_BIT)` 为真的角色 → `True`
   （`ADMIN_PERMISSION_BIT = 0`，即 `permissions & (1 << 0) != 0`；判断逻辑在 `khl.role.Role.has_permission`）
4. 否则 `False`

注意：消息事件携带的 `Guild` 是**懒加载**的（只含 id），`master_id` 必须调用 `await guild.load()` 后才有值，
因此 `_get_master_id` 内部做了加载与缓存。

## 缓存机制

三类数据都带缓存，避免每条消息都请求 KOOK API（有频率限制）。实现在 `common.TTLCache`，
**两层语义**，与 `config.json` 一一对应：

| 层 | 配置项 | 默认 | 行为 |
| --- | --- | --- | --- |
| 软上限 | `admin_cache_ttl` | 300 | 未过期直接命中；过期后**尝试刷新** |
| 硬上限 | `admin_cache_stale_grace` | 3600 | 刷新**失败**时旧值最多再用这么久；超过就失败关闭 |

| 缓存 | key | 内容 | 容量上限 |
| --- | --- | --- | --- |
| `_guild_role_cache` | `guild_id` | 服务器角色列表 | 256 |
| `_guild_master_cache` | `guild_id` | 服主 ID | 256 |
| `_user_role_cache` | `(guild_id, user_id)` | 成员的角色 ID 列表 | 4096 |

完整行为矩阵：

| 缓存状态 | KOOK API | 结果 |
| --- | --- | --- |
| 未过期 | 不调用 | 用缓存 |
| 已过期 | 正常 | 刷新并回写，角色变动最多延迟 `admin_cache_ttl` 秒生效 |
| 已过期，超期 ≤ grace | 失败 | 用旧值 + 打日志 |
| 已过期，超期 > grace | 失败 | **失败关闭** → 非管理员 |
| 无缓存 | 失败 | **失败关闭** → 非管理员 |

失败关闭是刻意的：管理员权限被撤销后，不能因为 KOOK API 一直报错就无限期沿用旧权限。
代价是 API 长时间挂掉时管理员指令会「没反应」（`on_rule_not_passed` 是静默的），
终端会打印 `[warn] ... 判定为非管理员（失败关闭）` 便于定位。

容量上限的必要性：`_user_role_cache` 的 key 是 `(guild_id, user_id)`，随活跃用户线性增长，
不设上限长期运行就是内存泄漏。`TTLCache` 超限时先清过期项，仍超就丢最早插入的。
上限写得比实际活跃用户大，正常社区规模下不会触发淘汰。

调试时把 `admin_cache_ttl` 置 0 即可每次都刷新（`admin_cache_stale_grace` 管的是刷新失败后的宽限）。

## 新增指令

khl.py 的 `@bot.command` 支持 `rules`（准入规则列表）与 `exc_handlers`（异常处理），
这是官方推荐的命令准入方式。

指令写在哪个模块都行（`main.py` 或功能子包里），**只要从 `commands.py` 拿 `ADMIN_ONLY`**：

```python
from epbot.bot import bot
from epbot.commands import ADMIN_ONLY

@bot.command(name="ep", desc="获取EP信息", **ADMIN_ONLY)
async def ep_command(msg: Message):
    await msg.reply("EP 信息...")
```

`ADMIN_ONLY` 就是 `dict(rules=..., exc_handlers=...)`，在 `commands.py` 里定义：

```python
ADMIN_ONLY = dict(
    rules=[admin_rule],
    exc_handlers={
        Exceptions.Handler.RuleNotPassed: on_rule_not_passed,
        Exceptions.Handler.ArgLenNotMatched: on_arg_len_not_matched,
    },
)
```

功能子包里的指令照旧用 `setup(bot, ADMIN_ONLY)` 传参（见下文 Welcome / Ticket 模块）——
虽然现在子包直接 import `commands` 也不会成环（被依赖的是 `bot.py`），
但保持传参可以把「注册什么」的决定权集中在 `main.register()` 一处。

### 命令参数

第一个参数固定为 `Message`，其余参数按空格切分并自动按类型转换（`str` / `int` / `float`）：

```python
@bot.command(name="echo", desc="复读", **ADMIN_ONLY)
async def echo_cmd(msg: Message, text: str = ""):
    await msg.reply(text)
```

参数个数不匹配会抛 `Exceptions.Handler.ArgLenNotMatched`。`ADMIN_ONLY` 里已经统一挂了这个异常的处理函数
`on_arg_len_not_matched`，它会区分「参数太少 / 太多」并回一句用法提示，`exc_handlers` 的处理函数
**必须是 async**，签名固定为 `(Command, Exception, Message)`。

用到的用法提示从 `COMMAND_USAGE` 按指令名取（`{'help': '/help', ...}`），**新增指令时在这里补一行**，
没登记就退化成 `/{指令名}`，不会报错。

## 事件处理器

`rules` 只对 `@bot.command` 生效。`bot.on_message` 等事件处理器用装饰器：

```python
@bot.on_message(...)
@admin_only
async def on_something(msg: Message):
    ...
```

`admin_only` 只是 `is_admin` 的一层薄封装：校验不通过就直接 `return`，同样不做任何响应。

## 欢迎功能（epbot/welcome/welcome.py）

功能模块统一采用 `setup(bot, admin_only)` 的形式注册，由 `main.register()` 调用：

```python
# src/epbot/main.py
from .ticket.ticket_manager import setup as setup_ticket
from .welcome.welcome import setup as setup_welcome

setup_welcome(bot, ADMIN_ONLY)
setup_ticket(bot, ADMIN_ONLY, is_guild_admin)   # 工单需要额外的管理员判定入口
```

`admin_only` 参数传的就是 `commands.ADMIN_ONLY`。

### 状态持久化

| 项 | 值 |
| --- | --- |
| 文件 | `data/welcome_channels.json`（路径来自 `paths.WELCOME_STATE_PATH`） |
| 结构 | `{"服务器 id": "频道 id"}` |
| 读写 | 模块级 `_targets` 内存字典 + `_load()` / `_save()`，实际 I/O 走 `common.read_json` / `write_json_atomic` |

因为是 `guild_id -> channel_id` 的单值映射，一个服务器天然只能有一个频道开启，无需额外校验。

### 入服事件

```python
@bot.on_event(EventTypes.JOINED_GUILD)
async def on_joined_guild(_bot: Bot, event: Event):
    ...
```

- 事件处理器的签名是 `(Bot, Event)`，与 `@bot.command` 的 `(Message, ...)` **不同**
- khl.py 不解析事件体，`event.body` 是原始 dict；本模块对 `guild_id` / `user_id` 做了
  `body` 与 `event.target_id` / `event.author_id` 的兼容取值，不同事件结构都能兼容
- 发消息用 `(await bot.client.fetch_public_channel(cid)).send(...)`，频道被删时 `fetch` 会报错，已 try/except
- 文本里的 `(met)用户id(met)` 是 KOOK 的 at 人语法

## 工单功能（epbot/ticket/）

职责划分：

| 文件 | 职责 |
| --- | --- |
| `ticket_config.json` | 纯配置：按钮名字 + value 暗号，以及卡片文案、频道前缀等（包数据，跟着代码走） |
| `ticket_cards.py` | 只把卡片拼成 `CardMessage`，不碰任何业务；对外只暴露 `get_menu_card()` 和 `get_ticket_card(content)` |
| `ticket_manager.py` | 业务：`/ticket on/off`、按钮点击、建频道、设权限、关票 |

两个模块各自读一次 `paths.TICKET_CONFIG_PATH`（卡片要按钮表，管理器要前缀/分类），
文件很小，读两次避免为了共享配置再加一层模块。

### 按钮点击事件

`EventTypes.MESSAGE_BTN_CLICK`，注意两个 `target_id` 含义不同：

| 取值 | 含义 |
| --- | --- |
| `event.target_id` | 服务器 id（事件本身的 target） |
| `event.body['target_id']` | 频道 id（卡片所在频道） |

代码里写成 `body.get('channel_id') or body.get('target_id')` 兼容不同事件结构。
点击事件靠 `body['value']` 区分按钮，所以面板按钮用配置里的 value 暗号，
关票按钮用 `ticket_cards.CLOSE_VALUE`（`ticket_close`）。

### 工单分组

工单频道不会散在根目录，而是统一挂在「工单」分组（`category_name`）下。
`_get_ticket_category()` 的优先级：

1. 配置里写了 `category_id` → `fetch_channel_category()` 拿过来
2. 状态里记过 `category_id` → `fetch_channel_category()` 验一下还在不在，在就复用
3. 都没有（或分组被删了）→ `guild.create_channel_category()` 新建，并把 id 记进状态

分组 id 存在 `guilds[服务器id].category_id`，`/ticket off` 只清 `menu_channel`，
分组会留着给下次复用。

三条路径都会调 `_ensure_category_private()`，保证**分组只对服主/管理员可见**：

```python
await category.create_role_permission(EVERYONE_ROLE_ID)          # role_id = 0 即 @全体成员
await category.update_role_permission(EVERYONE_ROLE_ID, allow=0, deny=PERM_VIEW)
```

先 `fetch_permission()` 读一遍，已经是私密的就直接返回，不重复写；
如果被管理员手动改成公开，下次开票会自动改回去。

> ⚠️ **顺序很重要**：官方文档写着「在分组 id 上改权限会同步给所有 sync=1 的子频道」，
> 所以设分组权限必须在 `create_text_channel()` **之前**完成，
> 否则会把子频道刚设好的用户级放行一起冲掉。
> 同理，如果以后有人在建完频道后才去改分组权限，需要重新给频道补一次放行。

**实测补充（2026-09）**：`create_text_channel()` 建出来的频道默认 `sync=1`，会立刻继承分组权限，
所以「先建频道、后设频道级权限」之间**没有公开窗口**；机器人写频道级权限时 `sync` 才翻成 0
（线上工单频道 `sync=False` 就是这么来的）。注意这个保证**依赖分组已经是私密的** ——
分组若还是公开的，`sync=1` 继承到的就是「人人可见」，那几秒内新频道对所有人可见。

**已知限制**：分组权限只在**开票时**由 `_get_ticket_category()` 设置，所以
手动被改回公开的分组（或历史遗留的公开分组）要等到**下一个人开票**才会被改回来，
已有的老工单不会自动补。需要立刻修正时，自己调一次 `_ensure_category_private(category)` 即可。

**刻意不给开票人放行分组**：开票人只在**频道级**被放行（`allow=VIEW|SEND`），
所以他能看到自己的工单频道，但**看不到**「工单」分组本身（分组对他的角色是 deny）。
这是有意为之：分组本身就是工单系统的内部结构，没必要对开票人暴露。

> 注意：`category_id` 指向的是管理员自己的分组时，也会被加上这条 deny —— 这是有意为之，
> 因为「工单分组对外不可见」是需求而不是可选项。

### 私密频道与权限

建完频道后调 `_set_private_permission()`，两段式：

1. `create_role_permission(0)` + `update_role_permission(0, allow=0, deny=PERM_VIEW)` —— 对 @全体成员 关掉查看
2. `create_user_permission(user_id)` + `update_user_permission(user_id, allow=PERM_VIEW | PERM_SEND)` —— 单独放行发起人

`create_*` 用 try/except 包住：权限项已存在时会报错，不能当致命错误处理。
管理员因为自身带管理员权限，不受这条 deny 影响，依然能看到所有工单频道。

**建频道与设权限是包在同一个 try 里的**：任何一步抛错就 `_discard_channel()` 把刚建出来的频道删掉，
否则会留下一个没人看得到的公开空频道（孤儿）——权限没设上的话，任何人都能看到里面的内容。

#### 权限回读校验

KOOK 的频道如果开了「同步分类权限」，频道级设置会被分类的设置覆盖。
所以发完工单卡片后会调 `_permission_applied()` 回读一次频道权限，确认
「@全体成员 deny PERM_VIEW」真的在里面；读不到就写日志 + 给发起人发一条仅他可见的警告。
宁可误报也不能静默地把工单频道开成公开的。
（`fetch_permission()` 本身出错时返回 `True`，避免网络抖动导致假报警。）

### 开票去重

同一个用户、同一个服务器、同一种工单类型，同时只能有一个未关闭的频道。
`_find_alive_ticket()` 会拿 `tickets` 里的记录去 `fetch_public_channel` 验一下：
频道已经被管理员手动删了的话，这条过期记录会被清掉，否则这个用户以后都开不了这种票。

命中去重时不会新建频道，而是用 `_notify_user()` 发一条**仅该用户可见**的提示，附上已有频道链接。

### 关票

工单卡片上的「关闭工单」按钮 value 是 `CLOSE_VALUE`，点击后删频道。校验分两层：

1. 频道必须在 `tickets` 里有记录（挡住伪造 value 误删普通频道）
2. 点击人必须是**工单发起人**，或者是**服主 / 管理员**（管理员可代关）

不满足任一条就静静返回，不做任何响应。

管理员判定用的是 `is_guild_admin(guild_id, user_id)` —— 这是 `admin.py` 里拆出来的入口：

```python
async def is_admin(msg: Message) -> bool:          # 命令/消息场景
    guild = getattr(msg.ctx, 'guild', None) ...
    return await _is_admin_in_guild(guild, msg.author_id)

async def is_guild_admin(guild_id, user_id) -> bool:  # 事件场景，只有 id
    guild = await bot.client.fetch_guild(guild_id)
    return await _is_admin_in_guild(guild, user_id)
```

两者共用 `_is_admin_in_guild()`，所以服主/权限位 0 的判定逻辑只有一份。
`ticket_manager.setup()` 多接收一个 `is_guild_admin` 参数就是为了这个（按钮点击事件看不到 `Message`）。

只有点击人不是发起人时，才会真正去调 `fetch_guild()` 查身份，避免正常关票多一次 API 请求。

### 状态存取

`data/ticket_state.json`（`paths.TICKET_STATE_PATH`）是**唯一数据源，不在内存里留存**：
`_read_state()` 每次现读文件，`_write_state()` 在改动后写回。好处是手工改文件、
或同时跑多个实例都不会出现内存与文件不一致。

```json
{ "guilds": { "服务器id": { "menu_channel": "频道id" } },
  "tickets": { "频道id": { "guild_id": ""、"user_id": ""、"type": "bug"、"name": "Bug" } } }
```

文件不存在、损坏、或顶层不是对象时，`_read_state()` 返回 `{"guilds": {}, "tickets": {}}`，不会抛异常。

### 并发安全

khl.py 派发消息/事件是 `asyncio.ensure_future`，**多个用户同时点击是真正并行的**，
而「读文件 → 改 → 写文件」不是原子操作，所以：

- 所有读-改-写都包在模块级的 `asyncio.Lock`（`_LOCK`）里，避免互相覆盖
- `_write_state()` 写临时文件后 `os.replace()`，避免中途挂掉/并发导致半截 JSON
  （半截 JSON 的后果不是报错，而是 `_read_state()` 静默返回空 —— 所有工单记录瞬间丢失）
- 锁里**不做网络请求**：建频道、设权限、发卡片都在锁外，否则一次开票（5 次 API 调用）
  会把所有人的开票请求排队塞住

**已知遗留**：去重校验与写入记录分处两个临界区，中间夹着建频道的网络请求。
极端情况下（同一用户几百毫秒内双击）可能建出两个频道；
代码里建完频道会在锁内**再查一次**，命中就删掉新频道并提示，所以只会白花一次 API，不会真的多出一个。

### 欢迎语与洗牌袋

欢迎语写在模块顶部的 `WELCOME_MESSAGES` 常量里，模板支持两个占位：

| 占位符 | 含义 |
| --- | --- |
| `{guild_name}` | 服务器名，`str.format()` 替换 |
| `(met)(met)` | at 新成员，实际替换为 `(met)用户id(met)` |

随机采用「洗牌袋」策略，而不是每次 `random.choice`：

- `_bags[guild_id]` 存本轮还没抽到的下标，用 `random.shuffle` 洗好后逐个 `pop()`
- 袋子空了才重新洗牌，因此**一轮内每条都必定出现且只出现一次**（样例：`1,4,3,2 | 4,3,1,2`）
- 重新洗牌时若袋尾（本轮的第一次抽）与上轮最后一次相同，就与邻位交换，避免跨轮次连续重屴

> 若 `random.choice`，长度为 6 的列表在前 6 次里出现重屴的概率约 60%，所以不能偷懒。
> 袋子状态只存内存，重启后会重新开始一轮。

## 频道被删除后的自愈

绑定关系（欢迎频道、工单频道）存在进程外的 JSON 里，所以「管理员趁机器人没开把频道删了，重启后记录还在」
是必然会遇到的情况，两个模块都得自己认出来并清理，否则就是永久占用：

| 记录 | 频道被删后的后果 | 处理 |
| --- | --- | --- |
| `welcome_channels.json` 里的频道 | `/welcome on` 提示「已在别处开启，请先去那关闭」，`/welcome off` 又说「本频道没有开启」→ **该服务器再也开不了自动欢迎**，只能手改 JSON | `/welcome on` 确认删除就清记录并接管，分不清时也接管但会警告（旧绑定对机器人已不可用）；`/welcome off` 分不清时**不动**记录；入服事件同理 |
| `ticket_state.json` 的 `menu_channel` | 面板卡片随频道一起没了，不会有按钮可点，无影响 | 无需处理（`/ticket on` 无条件覆盖，`/ticket off` 也无条件清理） |
| `ticket_state.json` 的 `tickets[频道]` | 同类型工单名额被永久占用 | 开票前查一次频道状态，**确认**没了才清记录；分不清则保留并提示用户 |

另外 `_close_ticket()` 是**先摘记录、再删频道**：频道可能已经被管理员手删过，反过来写的话
`delete_channel` 会抛错，记录就留在文件里把名额占住，用户看到的是「点了关闭没反应」。

### 判据：为什么不用错误码，而用频道清单交叉验证

最先想的是按错误码判断，实测后否掉了 —— KOOK 对下面三种情况返回的**完全一样**：

| 情况 | 返回 |
| --- | --- |
| 频道已删除 | `err_code=400`, `err_message='guild_id不存在或机器人没有权限查看'` |
| id 从不存在 | 同上，逐字一致 |
| 机器人没有查看权限 | 同上，逐字一致 |

（实测方法：建一个频道 → `fetch` 成功 → 删掉 → 再 `fetch`，与一个从未存在的 id 比对结果。
khl 只保存 `err_code` / `err_message`，包里也没有码表，所以无从映射。）

即任何「错误码白名单」都无效 —— 不是没选对码，而是**服务端本身就不区分**。

现在改为三态 + 交叉验证，实现在 `common.channel_state()`：

| 结果 | 含义 | 调用方行为 |
| --- | --- | --- |
| `CHANNEL_OK` | `fetch` 成功 | 正常走原逻辑 |
| `CHANNEL_GONE` | `fetch` 失败，**且服务器频道清单里没有这个 id** | 可以安全清理记录 |
| `CHANNEL_UNKNOWN` | 分不清：网络抖动 / 清单里还有这个 id / 清单也拉不到 | 保留记录，只提示，不动数据 |

清单走**原始 API**（`api.Channel.list` + `gate.exec_paged_req`），不用 `guild.fetch_channel_list()`：
后者会用 `ChannelTypes` 包装每个频道，而该枚举只定义了 `CATEGORY=0/TEXT=1/VOICE=2`，
服务器上只要有一个 `type=4` 的频道就抛 `ValueError: 4 is not a valid ChannelTypes`
（实测在 `EpochMC` 上必崩，同一个接口走原始 API 则正常）。

一个刻意接受的代价：`CHANNEL_GONE` 只代表「不在清单里」，而机器人看不到的频道也不会出现在清单里，
所以「权限被收回」会被判成 `GONE`。这是可接受的 —— 读不到的频道对机器人本来就已不可用。
清单结果按 guild 缓存 30 秒，避免一次批量失败时重复打 API；代价是刚删的频道最多 30 秒后才被确认。

## 注意事项

- `msg.ctx.guild` 在私聊消息中为 `None`，任何依赖服务器信息的功能都要先判空
- **不要删除 `exc_handlers` 里的 `RuleNotPassed` 处理器**：非管理员触发指令时会抛该异常，
  有处理器在（即使是空实现）才能确保被安静地吞掉，不会在终端留下堆栈
- `config.json` 中的 Token 属于敏感信息，不要提交到仓库；代码里的取值顺序是
  **环境变量 `KOOK_TOKEN` > `config.json` 的 `token`**，缺失时启动会打印 `[warn]` 提示
- 缓存刷新失败超过 `admin_cache_stale_grace` 后会**失败关闭**：管理员指令表现为「没反应」
  （静默的 `RuleNotPassed`），终端会有 `[warn] ... 判定为非管理员（失败关闭）`，别误判成机器人掉线
- **别用 `guild.fetch_channel_list()`**：khl 0.3.17 的 `ChannelTypes` 只定义了 0/1/2，
  服务器上存在 `type=4` 频道时会抛 `ValueError: 4 is not a valid ChannelTypes`。
  需要频道清单时用 `common._channel_ids()`（走原始 API，已在真实服务器上验证）
- 拼路径一律走 `paths.py`，不要在模块里用 `__file__` 现拼（否则目录一变就到处漏改）
- `import epbot.main` 不注册任何指令，测试里要显式调 `main.register()`

## Python 版本兼容

khl.py 的 `Bot.run()` 内部是 `self.loop = asyncio.get_event_loop()`，而 **Python 3.10+ 起
`get_event_loop()` 在没有已设置的事件循环时会直接抛 `RuntimeError`**（3.12 起弃用提示，3.14 直接报错）：

```
RuntimeError: There is no current event loop in thread 'MainThread'.
```

因此 `epbot/main.py` 的 `run()` 在 `bot.run()` 之前手动创建并设置事件循环：

```python
asyncio.set_event_loop(asyncio.new_event_loop())
bot.run()
```

不要改成 `asyncio.run(...)`：`bot.start()` 内部通过 `AsyncRunnable.schedule()` 自行调度任务，
重复创建循环会与 khl.py 的生命周期管理冲突。若要升级 khl.py，先确认新版本是否已自行创建事件循环。
