# EPbot

基于 [khl.py](https://github.com/TWT233/khl.py) 的 KOOK 机器人。

## 快速开始

从零到机器人上线就 6 步。所有命令都在**仓库根目录**（即 `README.md` 所在的目录）执行。

### 1. 前置条件

| 需要 | 说明 |
| --- | --- |
| Python 3.8+ | 安装时记得勾上「Add Python to PATH」。本机 `venv/` 用 **3.14.7** 实测可用 |
| 一个机器人 Token | 在 [KOOK 开发者后台](https://developer.kookapp.cn/app/index) → 应用 → 机器人 里获取 |
| 能访问 PyPI | 首次装依赖需要联网 |

### 2. 拿到代码

```bash
git clone https://github.com/GGGlavfh/KOOK_EPbot.git
cd KOOK_EPbot
```

不用 git 也行：仓库页点绿色 `Code` → `Download ZIP`，解压后进到那个目录。

### 3. 建虚拟环境并装依赖

**推荐用虚拟环境**：依赖和系统 Python 隔开，以后不想用了直接删 `venv/` 就等于卸载干净。

```powershell
# Windows PowerShell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

```bash
# Linux / macOS
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

装对了的话，命令行提示符前面会出现 **`(venv)`** —— 表示接下来所有命令都跑在这个环境里。

> **为什么写 `python -m pip` 而不是直接敲 `pip`**：能确保装进虚拟环境，而不是装到全局 Python（否则会出现「明明装了却 import 不到」）。
>
> **PowerShell 报 `Activate.ps1 cannot be loaded`（禁止运行脚本）**：执行一次
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` 再重试；或者改用 cmd 里的
> `venv\Scripts\activate.bat`。
>
> **不想用虚拟环境**：直接 `python -m pip install -r requirements.txt` 也能跑，但会和其它 Python 项目
> 互相干扰，不推荐。

`requirements.txt` 里只有一行 `-e .`（把本项目以可编辑方式装上，顺便装 khl.py），依赖声明的唯一来源是 `pyproject.toml`。装完还会多出一个 `epbot` 命令，它和 `python -m epbot` 完全等价。

### 4. 配置 Token

仓库里**没有** `config.json`（它含 Token，已被 `.gitignore` 排除），先从模板复制一份：

```powershell
Copy-Item src/epbot/config.example.json src/epbot/config.json   # Windows
# cp src/epbot/config.example.json src/epbot/config.json        # Linux / macOS
```

然后编辑 `src/epbot/config.json` 把 `token` 填上。各字段含义见下面的[配置项](#配置项)。

> 不想把 Token 写进文件，可以改用环境变量（优先级高于配置文件）：
>
> ```powershell
> $env:KOOK_TOKEN = "你的 Token"   # 只在当前窗口有效
> setx KOOK_TOKEN "你的 Token"    # 永久写入用户环境变量，需重开窗口
> ```

### 5. 启动

```powershell
python -m epbot
```

看到 `机器人正在连接 KOOK...` 且后面没有报错，就是上线了。`Ctrl + C` 停止。

> 启动前确认提示符里有 `(venv)`；没有的话回第 3 步。实在不想激活，也可以直接用
> 虚拟环境里的解释器跑：`.\venv\Scripts\python.exe -m epbot`（Linux：`./venv/bin/python -m epbot`）。

### 6. 让它一直在后台跑（可选）

上面的方式一关窗口就停了。想长期挂着，看系统选一种：

**Windows** —— 用「任务计划程序」开机自启：新建任务 → 触发器选「登录时」→ 操作选「启动程序」，
程序填 `<项目目录>\venv\Scripts\python.exe`，参数填 `-m epbot`，起始于填 `<项目目录>`。

**Linux** —— `screen`（推荐，便于随时查看日志）：

```bash
screen -S epbot
python -m epbot      # 启动后按 Ctrl+A 再按 D 挂起，窗口关了也还在跑
screen -r epbot      # 需要时连回来
```

或者用 `nohup`：

```bash
nohup python -m epbot > epbot.log 2>&1 &
```

### 以后更新代码

```bash
git pull
python -m pip install -r requirements.txt   # 只有依赖变动时才需要
python -m epbot
```

## 文件位置

| 内容 | 位置 |
| --- | --- |
| 代码 | `src/epbot/` |
| 配置模板（无敏感信息，随仓库提供） | `src/epbot/config.example.json` |
| 机器人配置（含 Token，**需自己创建**） | `src/epbot/config.json` |
| 运行状态（欢迎开关、工单记录） | `data/` |
| 绑定数据库（与游戏服共享） | 放在 **MC 插件目录**里（如 `D:/Minecraft/server/plugins/EPBind/bind.db`），机器人用环境变量 `EPBOT_BIND_DB` 指过去 |
| 工单按钮与文案 | `src/epbot/ticket/ticket_config.json` |

## 配置项

编辑 `src/epbot/config.json`（怎么创建见[快速开始](#快速开始)第 4 步）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `token` | string | 机器人的 Token，在 [KOOK 开发者后台](https://developer.kookapp.cn/app/index) → 应用 → 机器人 中获取；本地测试可直接填这里，正式部署建议改用环境变量 `KOOK_TOKEN`（优先级高于此处） |
| `verify_token` | string | Webhook 校验 Token（仅 webhook 模式需要） |
| `encrypt_token` | string | Webhook 加密 Token（仅 webhook 模式需要） |
| `webhook_port` | number | Webhook 监听端口（仅 webhook 模式需要） |
| `using_ws` | bool | `true` 使用 websocket 模式，`false` 使用 webhook 模式 |
| `admin_cache_ttl` | number | 角色信息的缓存秒数（软上限），默认 `300`，用于减少 API 请求 |
| `admin_cache_stale_grace` | number | 刷新失败时旧权限缓存最多还能再用几秒（硬上限），默认 `3600`；超过就按「不是管理员」处理（失败关闭） |
| `bind_code_ttl` | number | 绑定验证码的兜底有效期（秒），默认 `900`；仅当游戏服没写 `code_expires_at` 时生效 |

> ⚠️ `token` 属于敏感凭证，**不要提交到 Git 仓库或分享给他人**。`.gitignore` 里已经排除了
> `config.json`，请不要去改这条规则。
>
> 启动时**优先读环境变量 `KOOK_TOKEN`**，读不到才回落到 `config.json` 的 `token`，两种方式选一种就行。
>
> 还可以用环境变量挪动文件位置（生产部署有用，可以把可写的状态文件挪出代码目录）：
> `EPBOT_CONFIG` 指定配置文件路径，`EPBOT_DATA_DIR` 指定状态文件目录，
> `EPBOT_BIND_DB` 单独指定绑定数据库（见[跨平台绑定](#跨平台绑定)）。

## 常见问题

| 现象 | 处理 |
| --- | --- |
| 启动时打印 `[warn] 找不到配置文件 ...` | 还没建 `config.json`，按[快速开始](#快速开始)第 4 步复制模板 |
| 启动时打印 `[warn] 未配置 Token` | `config.json` 里的 `token` 是空的，或者环境变量 `KOOK_TOKEN` 没设置 |
| `ModuleNotFoundError: No module named 'epbot'` | 提示符里没有 `(venv)`，依赖没装进当前解释器。回第 3 步激活并重装；或直接用虚拟环境的解释器：`.\venv\Scripts\python.exe -m epbot` |
| PowerShell 报 `Activate.ps1 cannot be loaded` | 见[快速开始](#快速开始)第 3 步的说明 |
| 发指令机器人不回应 | 只认**服主**和带「管理员」权限的角色，且**私聊不响应**。刚改过角色权限的话最多等 5 分钟（缓存）才生效 |
| 想换台机器部署 | 整个目录拷过去即可；`venv/` 建议重新建（里面写死了路径），想保留工单记录就把 `data/` 一起拷 |

## 管理员

只有**服主**，和角色中带有「管理员」权限的成员可以使用指令。
其他人即使发了指令，机器人也**不会有任何回应**（和自动回复无关的普通消息当然也不理）。

私聊无法识别身份，所以**私聊里的指令不会响应**。

## 指令

| 指令 | 说明 |
| --- | --- |
| `/help` | 显示帮助信息 |
| `/welcome on` | 在**当前频道**开启自动欢迎 |
| `/welcome off` | 关闭当前频道的自动欢迎 |
| `/ticket on` | 在**当前频道**放出发票面板（卡片） |
| `/ticket off` | 关闭本服务器的工单入口 |
| `/bind <验证码>` | 绑定游戏账号（**所有成员**可用，仅限绑定频道） |
| `/bind channel` | 把当前频道设为绑定频道（管理员） |
| `/bind off` | 关闭绑定功能（管理员） |

## 自动欢迎

1. 在想要发欢迎消息的频道里发送 `/welcome on`
2. 之后有新成员加入服务器，机器人就会在该频道发一条欢迎消息
3. 发送 `/welcome off` 可以关闭

欢迎语是有好几条的，每次新成员加入会**随机挑一条**，并且一轮里每条都发过之后才会重新开始，
所以不会出现某几条反复刷、其他永远轮不到的情况。

> 一个服务器**同时只能有一个频道**开启，想换频道需要先在原频道关闭。开关状态会保存到
> `data/welcome_channels.json`，重启机器人不会丢失。
>
> 如果原来开启的频道被删掉了（不管是在机器人开着还是关着的时候删的），也不会卡住：
> 在别的频道发 `/welcome on` 会自动清掉旧记录并改到本频道，发 `/welcome off` 也会顺手清理。

## 工单

1. 在工单频道里发送 `/ticket on`，机器人会发一张带 **Bug / 举报 / 赞助** 三个按钮的卡片
2. 成员点按钮，机器人自动建一个「工单」分组（首次），在里面建一个只有他能看到的频道
3. 处理完点击工单卡片上的「关闭工单」，频道会被删除（分组会保留，下次继续用）

> **工单分组默认只对服主和管理员可见**：机器人会给分组设上「@全体成员 禁止查看」，
> 普通成员不会在频道列表里看到这个分组；工单频道再单独放行发起人。
> 如果分组被手动改成公开，机器人下次开票时会自动改回去。

> 同一个人、同一种类型同时只能有一个未关闭的工单，再点会提示已有工单的频道链接。
> 关闭按钮**发起人、服主、管理员**都可以点，管理员可以代关别人的票。
> 提示信息只在点击者自己那边显示，不会刷屏、也不会把面板卡片顶掉。

> **工单频道被手动删掉也不会卡住**：机器人下次查到你那条记录时会自动清理；
> 点「关闭工单」时也是先清记录再删频道，所以不会出现「点了没反应、同类工单还开不了」的情况。

想改按钮名字或增删类型，编辑 `src/epbot/ticket/ticket_config.json` 里的 `buttons` 即可：

```json
"buttons": [
  { "name": "Bug", "value": "bug" },
  { "name": "举报", "value": "report" },
  { "name": "赞助", "value": "sponsor" }
]
```

| 配置项 | 说明 |
| --- | --- |
| `buttons` | 按钮名字与 value 暗号，`value` 保证唯一即可 |
| `category_name` | 工单分组名，默认 `工单`；分组不存在时机器人会自己建，并设为「仅服主/管理员可见」 |
| `category_id` | 手动指定一个已存在的分组 id，填了就忽略 `category_name`；⚠️ 机器人同样会给它设上「@全体成员 禁止查看」 |
| `channel_prefix` | 工单频道名前缀，默认 `工单-` |
| `menu_title` / `menu_text` | 面板卡片的标题与正文 |
| `ticket_title` | 开票后卡片的标题 |
| `close_button` | 关票按钮的名字 |

## 跨平台绑定

把**游戏账号**和 **KOOK 账号**对应起来。流程分两边：

1. 玩家在**游戏里**获取一个验证码（游戏服插件生成）
2. 玩家在 KOOK 的**绑定频道**发送 `/bind <验证码>`
3. 配对成功，两个账号就绑上了；游戏服那边自己查数据库就能知道是谁

### 管理员先开一次

在打算用作绑定的频道里发送：

```
/bind channel
```

之后成员的验证码只在这个频道里有效；关闭用 `/bind off`。

### 成员怎么用

```
/bind 483920
```

回复**只发给发送者本人**，不会在频道里刷屏：

| 情况 | 回复 |
| --- | --- |
| 成功 | 绑定成功！你的 KOOK 账号已与游戏账号 `xxx` 绑定。 |
| 验证码不对 / 已被用过 | 验证码不正确，或者已经被使用过了。请在游戏内重新获取。 |
| 验证码过期 | 验证码已过期，请在游戏内重新获取。 |
| 已经绑过 | 你在这个服务器已经绑定过游戏账号了（已绑定：`xxx`）。 |
| 不在绑定频道 | 请到 #绑定频道 去绑定。 |

> 目前是**一对一**：一个 KOOK 账号只能绑一个游戏账号，一个游戏账号同时只保留一条绑定记录。

### 数据放在哪

绑定数据就是一个 SQLite 文件，**游戏服插件和机器人读写的是同一个文件**，放在 MC 插件目录里：

```
Java 插件配置：D:/Minecraft/server/plugins/EPBind/bind.db

机器人这边（启动前设置，指向同一个文件）：
set EPBOT_BIND_DB=D:\Minecraft\server\plugins\EPBind\bind.db
python -m epbot
```

这样插件是自包含的，以后换台机器部署机器人也不用动插件配置；库所在目录不存在时机器人会自动创建。

> ⚠️ **两边必须用绝对路径，并且填的是同一个文件。**
> 两个进程的「当前目录」不一样：机器人从仓库根启动，MC 插件从服务端目录启动。
> 如果都写相对路径 `data/bind.db`，就会各自解析到不同位置 —— 一个在写 A 文件、另一个在读 B 文件，
> 表现就是「不管怎么试，机器人都说验证码不对」。（Java 里写 `D:/...` 或 `D:\\...` 都可以，
> 字符串里用反斜杠要写成双写。）

> 没设 `EPBOT_BIND_DB` 时默认还是 `data/bind.db` —— 那是还没接游戏服时的状态，接上之后两边都要指向同一个库。

表结构（即两端之间的接口）在 `src/epbot/bind/schema.sql`，可以直接把这个文件给 Java 端用；
Java 端的接入示例见 [DEVELOPER.md](./DEVELOPER.md)。

---

本项目基于 khl.py 开发，二次修改请看 [DEVELOPER.md](./DEVELOPER.md)。
