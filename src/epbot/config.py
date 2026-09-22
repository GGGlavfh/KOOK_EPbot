"""配置加载

Token 优先取环境变量 `KOOK_TOKEN`，取不到才回落到 `config.json`，
这样正式部署不必把凭证写进文件。
"""
import json
import os

from .paths import CONFIG_EXAMPLE_PATH, CONFIG_PATH

# 环境变量名：Token 优先从它读取
TOKEN_ENV = 'KOOK_TOKEN'
# 「管理员」权限的比特位（permissions 比特位 0 = 1）
ADMIN_PERMISSION_BIT = 0


def _load() -> dict:
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # 仓库里不带 config.json（含 Token，已被 .gitignore 排除），所以首次运行必然走到这里，
        # 提示要说清楚「从模板复制」或「用环境变量」，否则下载的人会一头雾水
        print(f"[warn] 找不到配置文件 {CONFIG_PATH}")
        print(f"[warn] 请复制模板：copy \"{CONFIG_EXAMPLE_PATH}\" \"{CONFIG_PATH}\"")
        print(f"[warn]   或者不用配置文件，直接设置环境变量 {TOKEN_ENV} 提供 Token")
        return {}
    except json.JSONDecodeError as e:
        print(f"[warn] 读取 {CONFIG_PATH.name} 失败({e})，将使用默认配置")
        return {}


CONFIG = _load()
TOKEN = os.environ.get(TOKEN_ENV) or CONFIG.get('token', '')
# 权限缓存时间（秒）：软上限，超过就尝试刷新
CACHE_TTL = CONFIG.get('admin_cache_ttl', 300)
# 刷新失败时旧值最多还能再用多久（秒）：硬上限，超过就按「不是管理员」处理（失败关闭）
CACHE_STALE_GRACE = CONFIG.get('admin_cache_stale_grace', 3600)
# 绑定验证码的兜底有效期（秒）：Java 端没写 code_expires_at 时用 created_at + 它判过期
BIND_CODE_TTL = CONFIG.get('bind_code_ttl', 900)
