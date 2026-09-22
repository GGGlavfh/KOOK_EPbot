"""Bot 单例

整个包共用这一个 `bot` 实例。单独放一个模块是为了让 `admin` / `commands` / 各功能模块
都能拿到它，而不用反向导入 `main`（那会形成循环依赖）。
"""
from khl import Bot

from .config import TOKEN, TOKEN_ENV

if not TOKEN:
    print(f"[warn] 未配置 Token：请设置环境变量 {TOKEN_ENV}，或在 config.json 中填写 token")

bot = Bot(token=TOKEN)
