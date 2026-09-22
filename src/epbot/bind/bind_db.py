"""绑定数据层：唯一直接碰 SQL 的地方

数据库是**跨语言共享**的（Java 端写验证码，机器人这边消费），所以这里有两条铁律：

1. **表结构是与 Java 端的契约**，DDL 放在同目录的 `schema.sql`，改动必须同步文档和 Java 侧
2. **两端会同时读写**，所以开 WAL + `busy_timeout`，并且用「带条件的单条 UPDATE」做原子抢占 ——
   先 SELECT 再 UPDATE 的写法在并发下会让两个请求同时成功

每次操作开一个新连接（用完就关）：指令频率很低，这样最简单，也不会长期占着锁。
"""
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from ..paths import BIND_DB_PATH, BIND_SCHEMA_PATH

# claim() 的返回状态
OK = 'ok'
NOT_FOUND = 'not_found'          # 没有这个验证码，或已经被用掉了
EXPIRED = 'expired'              # 找到了，但已过期
ALREADY_BOUND = 'already_bound'  # 这个 KOOK 账号已经绑过了
TAKEN = 'taken'                  # 并发下被别人抢先一步


@contextmanager
def _connect():
    """开连接：自动提交 + 5 秒忙等待

    `isolation_level=None` 是自动提交模式 —— 我们每条 SQL 都是自足的，
    不留长事务也就不会把 Java 端卡在 database is locked 上。
    """
    path = Path(BIND_DB_PATH)  # 允许外部（测试/工具）把它换成 str
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA busy_timeout = 5000')
    conn.execute('PRAGMA journal_mode = WAL')
    conn.execute('PRAGMA synchronous = NORMAL')
    try:
        yield conn
    finally:
        conn.close()


def init_schema():
    """建表建索引；可重复执行（Java 端也能拿 schema.sql 自己建）"""
    with _connect() as conn:
        conn.executescript(BIND_SCHEMA_PATH.read_text(encoding='utf-8'))


def claim(code: str, kook_id: str, fallback_ttl: int):
    """用验证码把 `kook_id` 绑上去，返回 `(状态, 附加信息)`

    按需求：成功时**清掉临时验证码**（`code` / `code_expires_at` 置 NULL），并把 KOOK id 写进同一条记录。
    过期的那条会整行删掉，免得留下永远对不上的垃圾数据。

    `fallback_ttl`：`code_expires_at` 为空时，用 `created_at + fallback_ttl` 兜底判过期。
    """
    code = (code or '').strip().upper()
    now = int(time.time())

    with _connect() as conn:
        # 1. 这个 KOOK 账号是否已经绑过（一对一）
        bound = conn.execute(
            'SELECT external_id FROM bindings WHERE kook_id = ?', (kook_id,)).fetchone()
        if bound:
            return ALREADY_BOUND, bound['external_id']

        # 2. 找还没被用掉的验证码（用 UPPER 比较，玩家输入大小写不影响）
        row = conn.execute(
            'SELECT id, external_id, code_expires_at, created_at FROM bindings '
            'WHERE code IS NOT NULL AND UPPER(code) = ?', (code,)).fetchone()
        if row is None:
            return NOT_FOUND, None

        # 3. 过期就删掉这条临时记录
        expires_at = row['code_expires_at'] or (row['created_at'] + fallback_ttl)
        if now > expires_at:
            conn.execute('DELETE FROM bindings WHERE id = ? AND kook_id IS NULL', (row['id'],))
            return EXPIRED, None

        # 4. 原子抢占：WHERE 里带条件，rowcount 不为 1 就说明被人抢先了
        try:
            cur = conn.execute(
                'UPDATE bindings SET kook_id = ?, code = NULL, code_expires_at = NULL, bound_at = ? '
                'WHERE id = ? AND code IS NOT NULL AND kook_id IS NULL',
                (kook_id, now, row['id']))
        except sqlite3.IntegrityError:
            # 撞上 ux_bindings_kook：这个 KOOK 账号在别处已经绑过了
            return ALREADY_BOUND, None
        if cur.rowcount != 1:
            return TAKEN, None
        return OK, row['external_id']


# ==================== 绑定频道 ====================
def get_bind_channel(guild_id: str):
    """取本服务器的绑定频道 id；没设置过返回 None"""
    with _connect() as conn:
        row = conn.execute(
            'SELECT channel_id FROM bind_channels WHERE guild_id = ?', (guild_id,)).fetchone()
    return row['channel_id'] if row else None


def set_bind_channel(guild_id: str, channel_id: str):
    """设置绑定频道（每服务器一个，重复设置会覆盖）"""
    with _connect() as conn:
        conn.execute(
            'INSERT INTO bind_channels(guild_id, channel_id, updated_at) VALUES(?, ?, ?) '
            'ON CONFLICT(guild_id) DO UPDATE SET channel_id = excluded.channel_id, '
            'updated_at = excluded.updated_at',
            (guild_id, channel_id, int(time.time())))


def clear_bind_channel(guild_id: str) -> bool:
    """关闭绑定功能；返回之前是否设置过"""
    with _connect() as conn:
        cur = conn.execute('DELETE FROM bind_channels WHERE guild_id = ?', (guild_id,))
    return cur.rowcount > 0
