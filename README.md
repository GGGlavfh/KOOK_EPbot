# EPbot

基于 [khl.py](https://github.com/TWT233/khl.py) 的 KOOK 机器人。

## 环境要求

- Python 3.8+
- khl.py

```bash
pip install -r requirements.txt
```

`requirements.txt` 里只有一行 `-e .`：会把本项目以「可编辑」方式装上，顺便装好 khl.py。
真正的依赖声明在 `pyproject.toml`（单一来源），装完就能用 `python -m epbot` 启动。

## 文件位置

| 内容 | 位置 |
| --- | --- |
| 代码 | `src/epbot/` |
| 配置模板（无敏感信息，随仓库提供） | `src/epbot/config.example.json` |
| 机器人配置（含 Token，**需自己创建**） | `src/epbot/config.json` |
| 运行状态（欢迎开关、工单记录） | `data/` |
| 工单按钮与文案 | `src/epbot/ticket/ticket_config.json` |

## 配置

仓库里**没有** `config.json` —— 它含 Token，已被 `.gitignore` 排除。首次使用先从模板复制一份：

```powershell
Copy-Item src/epbot/config.example.json src/epbot/config.json   # Windows
# cp src/epbot/config.example.json src/epbot/config.json        # Linux / macOS
```

然后编辑 `src/epbot/config.json`：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `token` | string | 机器人的 Token，在 [KOOK 开发者后台](https://developer.kookapp.cn/app/index) → 应用 → 机器人 中获取；本地测试可直接填这里，正式部署建议改用环境变量 `KOOK_TOKEN`（优先级高于此处） |
| `verify_token` | string | Webhook 校验 Token（仅 webhook 模式需要） |
| `encrypt_token` | string | Webhook 加密 Token（仅 webhook 模式需要） |
| `webhook_port` | number | Webhook 监听端口（仅 webhook 模式需要） |
| `using_ws` | bool | `true` 使用 websocket 模式，`false` 使用 webhook 模式 |
| `admin_cache_ttl` | number | 角色信息的缓存秒数（软上限），默认 `300`，用于减少 API 请求 |
| `admin_cache_stale_grace` | number | 刷新失败时旧权限缓存最多还能再用几秒（硬上限），默认 `3600`；超过就按「不是管理员」处理（失败关闭） |

> ⚠️ `token` 属于敏感凭证，只应放在环境变量或本地文件里，**不要提交到 Git 仓库或分享给他人**。
>
> 推荐用环境变量提供（Windows PowerShell）：
>
> ```powershell
> $env:KOOK_TOKEN = "你的 Token"   # 当前窗口有效
> setx KOOK_TOKEN "你的 Token"    # 永久写入用户环境变量，需重开窗口
> ```
>
> 启动时优先读 `KOOK_TOKEN`，读不到才回落到 `config.json` 的 `token`。
>
> 配置文件和状态文件的位置也都能用环境变量改（生产部署时很有用，可以把可写的状态
> 挪到代码目录之外）：`EPBOT_CONFIG` 指定配置文件路径，`EPBOT_DATA_DIR` 指定状态文件目录。

## 运行

在**仓库根目录**（即 `README.md` 所在的目录）执行：

```bash
python -m epbot
```

装包时会顺带生成一个 `epbot` 命令，敲它也是一样的：

```bash
epbot
```

保持窗口开着，机器人就会一直在线。`Ctrl + C` 退出。

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

---

本项目基于 khl.py 开发，二次修改请看 [DEVELOPER.md](./DEVELOPER.md)。
