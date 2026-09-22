"""路径解析

代码在 `src/epbot/`，运行时数据（状态文件）默认放在仓库根的 `data/`，两者分开是为了
让包目录保持干净、可打包，不含运行时数据。

| 用途 | 默认位置 | 覆盖方式 |
| --- | --- | --- |
| 机器人配置 | `src/epbot/config.json` | 环境变量 `EPBOT_CONFIG` |
| 状态文件 | 仓库根 `data/` | 环境变量 `EPBOT_DATA_DIR` |

状态文件是可写的运行时数据，配置里含 Token，所以生产部署时可以靠这两个环境变量
把它们挪到包目录之外（例如只读的代码目录 + 可写的 `data/`）。
"""
import os
from pathlib import Path

# .../src/epbot
PACKAGE_DIR = Path(__file__).resolve().parent
# 仓库根：src/epbot 往上两级。项目以「源码目录 + 虚拟环境」或 `pip install -e .` 方式部署，
# 两种情况下这个推导都成立。
PROJECT_ROOT = PACKAGE_DIR.parent.parent

CONFIG_PATH = Path(os.environ.get('EPBOT_CONFIG') or PACKAGE_DIR / 'config.json')
# 配置模板：随包发布，首次使用复制成 config.json；始终指向包内，不受 EPBOT_CONFIG 影响
CONFIG_EXAMPLE_PATH = PACKAGE_DIR / 'config.example.json'
DATA_DIR = Path(os.environ.get('EPBOT_DATA_DIR') or PROJECT_ROOT / 'data')

WELCOME_STATE_PATH = DATA_DIR / 'welcome_channels.json'
TICKET_STATE_PATH = DATA_DIR / 'ticket_state.json'
# 按钮/文案属于「跟着代码走的配置」，留在包内
TICKET_CONFIG_PATH = PACKAGE_DIR / 'ticket' / 'ticket_config.json'


def ensure_data_dir() -> None:
    """确保数据目录存在，让启动阶段就暴露权限问题（而不是第一次开票时才发现）"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
