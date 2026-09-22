"""EPbot —— 基于 khl.py 的 KOOK 机器人

包内模块职责：

| 模块 | 职责 |
| --- | --- |
| `paths` | 路径解析：配置文件位置、数据目录 |
| `config` | 配置加载：Token（环境变量优先）、缓存时长 |
| `bot` | 全局 Bot 单例 |
| `common` | 跨模块共用小工具：JSON 读写、频道存活判断 |
| `admin` | 管理员校验与 TTL 缓存 |
| `commands` | 指令准入规则与异常处理 |
| `welcome` | 自动欢迎功能 |
| `ticket` | 工单功能 |
| `main` | 装配（`register`）与启动（`run`） |

启动方式：`python -m epbot`
"""

__version__ = '1.0.0'
