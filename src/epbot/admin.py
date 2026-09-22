"""管理员校验

管理员 = 服主 + 任一角色带「管理员」权限（permissions 比特位 0）的成员。

三类数据都带缓存，避免每条消息都打 KOOK API（有频率限制）。缓存分两层语义：

| 层 | 配置项 | 默认 | 行为 |
| --- | --- | --- | --- |
| 软上限 | `admin_cache_ttl` | 300 | 未过期直接命中；过期后**尝试刷新** |
| 硬上限 | `admin_cache_stale_grace` | 3600 | 刷新**失败**时旧值还能再用多久，超过就失败关闭 |

失败关闭（返回空 → 判定为非管理员）是刻意的：管理员权限被撤销后，不能因为 KOOK API
一直报错就无限期沿用旧权限。显式拒绝比静默放行安全；代价是 API 长时间挂掉时管理员指令
会没反应（`on_rule_not_passed` 是静默的），终端会打印
`[warn] ... 判定为非管理员（失败关闭）`，便于定位。
"""
import functools

from khl import Message

from .bot import bot
from .common import TTLCache
from .config import ADMIN_PERMISSION_BIT, CACHE_STALE_GRACE, CACHE_TTL

# 服务器维度：一个 bot 通常只在少数服务器里，给个宽松上限即可
_GUILD_MAX = 256
# 成员维度：随活跃用户增长，必须有上限，否则长期运行就是内存泄漏
_USER_MAX = 4096

_guild_role_cache = TTLCache(CACHE_TTL, _GUILD_MAX)
_guild_master_cache = TTLCache(CACHE_TTL, _GUILD_MAX)
_user_role_cache = TTLCache(CACHE_TTL, _USER_MAX)


async def _get_guild_roles(guild):
    """获取服务器角色列表（带缓存）；取不到时返回 `[]`，调用方据此失败关闭"""
    roles, stale = _guild_role_cache.get(guild.id, allow_stale_for=CACHE_STALE_GRACE)
    if roles is not None and not stale:
        return roles
    try:
        roles = await guild.fetch_roles()
    except Exception as e:
        print(f"[warn] 获取服务器角色失败: {e}")
        if roles is not None:
            print(f"[warn] 沿用过期不超过 {int(CACHE_STALE_GRACE)} 秒的旧缓存")
            return roles
        print("[warn] 无可用缓存，判定为非管理员（失败关闭）")
        return []
    _guild_role_cache.set(guild.id, roles)
    return roles


async def _get_master_id(guild):
    """获取服主 ID（带缓存）；取不到时返回 `''`，调用方据此失败关闭

    消息事件携带的 `Guild` 是懒加载的（只含 id），`master_id` 必须 `await guild.load()`
    之后才有值，所以这里内部做加载。
    """
    master_id, stale = _guild_master_cache.get(guild.id, allow_stale_for=CACHE_STALE_GRACE)
    if master_id is not None and not stale:
        return master_id
    if not guild.loaded:
        try:
            await guild.load()
        except Exception as e:
            print(f"[warn] 获取服务器信息失败: {e}")
            if master_id is not None:
                print(f"[warn] 沿用过期不超过 {int(CACHE_STALE_GRACE)} 秒的旧缓存")
                return master_id
            print("[warn] 无可用缓存，判定为非管理员（失败关闭）")
            return ''
    _guild_master_cache.set(guild.id, guild.master_id)
    return guild.master_id


async def _get_user_role_ids(guild, user_id):
    """获取成员在服务器中的角色 ID 列表（带缓存）；取不到时返回 `[]`，失败关闭"""
    key = (guild.id, user_id)
    role_ids, stale = _user_role_cache.get(key, allow_stale_for=CACHE_STALE_GRACE)
    if role_ids is not None and not stale:
        return role_ids
    try:
        guild_user = await guild.fetch_user(user_id)
        fetched = list(guild_user.roles or [])
    except Exception as e:
        print(f"[warn] 获取成员信息失败: {e}")
        if role_ids is not None:
            print(f"[warn] 沿用过期不超过 {int(CACHE_STALE_GRACE)} 秒的旧缓存")
            return role_ids
        print("[warn] 无可用缓存，判定为非管理员（失败关闭）")
        return []
    _user_role_cache.set(key, fetched)
    return fetched


async def _is_admin_in_guild(guild, user_id: str) -> bool:
    """按 Guild 对象判断成员是否为管理员（服主 或 拥有「管理员」权限的角色）"""
    if guild is None:  # 私聊拿不到服务器信息，无法判断身份
        return False

    user_id = str(user_id)

    # 1. 服主
    if user_id == await _get_master_id(guild):
        return True

    # 2. 任一角色带「管理员」权限
    role_ids = await _get_user_role_ids(guild, user_id)
    if not role_ids:
        return False
    for role in await _get_guild_roles(guild):
        if role.id in role_ids and role.has_permission(ADMIN_PERMISSION_BIT):
            return True
    return False


async def is_admin(msg: Message) -> bool:
    """判断消息发送者是否为管理员"""
    guild = getattr(msg.ctx, 'guild', None) if hasattr(msg, 'ctx') else None
    return await _is_admin_in_guild(guild, msg.author_id)


async def is_guild_admin(guild_id: str, user_id: str) -> bool:
    """按服务器 id + 用户 id 判断管理员

    按钮点击这类事件里只有 id、没有 Message，所以单独留一个入口。
    """
    try:
        guild = await bot.client.fetch_guild(guild_id)
    except Exception as e:
        print(f"[warn] 获取服务器信息失败: {e}")
        return False
    return await _is_admin_in_guild(guild, user_id)


def admin_only(func):
    """装饰器：仅管理员的消息才会执行（供 `bot.on_message` 等事件处理器使用）

    `rules` 只对 `@bot.command` 生效，事件处理器用这个。
    """
    @functools.wraps(func)
    async def wrapper(msg: Message, *args, **kwargs):
        if not await is_admin(msg):
            return
        return await func(msg, *args, **kwargs)
    return wrapper
