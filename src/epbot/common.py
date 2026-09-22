"""跨模块共用的小工具：JSON 读写、频道状态判断、带上限的 TTL 缓存

两个功能模块原先各自抄了一份 `_is_channel_gone` / 状态读写，这里集中到一处。
"""
import json
import os
import time

from khl import api
from khl.requester import HTTPRequester


def read_json(path, default=None):
    """读 JSON；文件不存在或内容损坏时返回 `default`，不抛异常

    注意「静默返回默认值」是刻意设计：状态文件损坏时应该当作没有记录，
    而不是让整个机器人因为一条脏数据起不来。
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default
    return default if data is None else data


def write_json_atomic(path, data) -> None:
    """原子写：先写临时文件再 `os.replace()` 覆盖

    直接写原文件的话，中途挂掉或并发会留下半截 JSON，而半截 JSON 不会报错，
    只会让下一次 `read_json()` 静默返回默认值 —— 记录会「全部丢失」。
    """
    dirname = os.path.dirname(str(path))
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


class TTLCache:
    """带容量上限的 TTL 缓存

    - `get(key)` 只认未过期的值（过期返回 `None`）
    - `get(key, allow_stale_for=N)` 允许把「过期不超过 N 秒」的旧值也取出来，
      并用返回的 `stale` 标记告知调用方 —— 这是**软上限 / 硬上限**两层语义的基础
    - 超过 `maxsize` 时先清掉已过期的项，仍然超就丢最早插入的那个
      （`dict` 保持插入顺序，所以 `next(iter(...))` 就是最旧的）

    为什么不用 `cachetools`：本项目直接依赖只有 khl.py，为这十几行逻辑再引一个包不划算；
    而且 `cachetools.TTLCache` 过期即 `KeyError`，拿不到「过期旧值」就实现不了宽限期语义。
    """

    def __init__(self, ttl: float, maxsize: int = 4096):
        self.ttl = ttl
        self.maxsize = maxsize
        self._data = {}  # key -> (value, saved_at)

    def get(self, key, allow_stale_for: float = 0):
        """返回 `(值, 是否为超出软上限的旧值)`；取不到时返回 `(None, False)`"""
        item = self._data.get(key)
        if item is None:
            return None, False
        value, saved_at = item
        age = time.time() - saved_at
        if age <= self.ttl:
            return value, False
        if allow_stale_for and age <= self.ttl + allow_stale_for:
            return value, True
        return None, False

    def set(self, key, value):
        self._data[key] = (value, time.time())
        self._trim()

    def _trim(self):
        """先清过期项，还超容量就丢最旧的"""
        if len(self._data) <= self.maxsize:
            return
        now = time.time()
        for key in [k for k, (_, saved_at) in self._data.items() if now - saved_at > self.ttl]:
            del self._data[key]
        while len(self._data) > self.maxsize:
            self._data.pop(next(iter(self._data)))


# ==================== 频道状态 ====================
# 三态：不能用 bool，因为「读不到」不等于「已删除」
CHANNEL_OK = 'ok'            # 能正常读到
CHANNEL_GONE = 'gone'        # 已确认不在服务器频道清单里
CHANNEL_UNKNOWN = 'unknown'  # 分不清（网络抖动、权限变更、清单也拉不到）

# 频道清单缓存：一次开票失败可能连着查好几条记录，避免重复打 API。
# TTL 取小值，保证「刚删掉的频道」最多 30 秒后就会被确认。
_channel_list_cache = TTLCache(ttl=30, maxsize=64)


async def _channel_ids(bot, guild_id: str) -> set:
    """取服务器的频道 id 集合（带短缓存）"""
    cached, _ = _channel_list_cache.get(guild_id)
    if cached is not None:
        return cached
    raw = await bot.client.gate.exec_paged_req(api.Channel.list(guild_id=guild_id))
    ids = {item.get('id') for item in raw}
    _channel_list_cache.set(guild_id, ids)
    return ids


async def channel_state(bot, guild_id: str, channel_id: str) -> str:
    """判断频道当前状态，返回 `CHANNEL_OK` / `CHANNEL_GONE` / `CHANNEL_UNKNOWN`

    为什么不能只看错误码：KOOK 对「频道已删除」「id 从不存在」「机器人没有查看权限」
    返回的**完全一样** —— 实测建一个频道再删掉，与一个从未存在的 id 结果相同：

        APIRequestFailed err_code=400, err_message='guild_id不存在或机器人没有权限查看'

    所以单次 `fetch` 在原理上就分不出「删了」还是「没权限」，任何错误码白名单都无效。

    改用**交叉验证**：fetch 失败时再看该服务器的频道清单里还有没有这个 id。
    - 清单里没有 → `CHANNEL_GONE`（可以安全清理记录）
    - 清单里有，或清单本身拉不到 → `CHANNEL_UNKNOWN`（调用方保守处理，不要删记录）

    走原始 `api.Channel.list` 而不是 `guild.fetch_channel_list()`：后者会用
    `ChannelTypes` 包装每个频道，而该枚举只定义了 0/1/2，服务器上只要有一个
    `type=4` 的频道就会抛 `ValueError: 4 is not a valid ChannelTypes`（实测踩到）。

    注意：机器人看不到的频道也不会出现在清单里，所以「权限被收回」会被判成 `GONE`。
    这是可接受的 —— 读不到的频道对机器人本来就已不可用。
    """
    try:
        await bot.client.fetch_public_channel(channel_id)
        return CHANNEL_OK
    except Exception as e:
        if not isinstance(e, HTTPRequester.APIRequestFailed):
            return CHANNEL_UNKNOWN  # 网络层异常，什么都不能证明
    try:
        ids = await _channel_ids(bot, guild_id)
    except Exception as e:
        print(f"[warn] 拉取服务器频道清单失败，无法确认频道状态: {e}")
        return CHANNEL_UNKNOWN
    return CHANNEL_GONE if channel_id not in ids else CHANNEL_UNKNOWN
