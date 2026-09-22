-- EPbot 跨平台绑定：表结构契约
--
-- 这个文件是两端共享的契约，改这里必须同步改 DEVELOPER.md 的说明与 Java 侧代码。
--   * Python 端：epbot/bind/bind_db.py 启动时执行它（都是 IF NOT EXISTS，可重复执行）
--   * Java 端：首次接入执行一次（逐条执行，见 DEVELOPER.md 的 Java 示例）
--
-- 列语义：
--   external_id      Java 端（游戏服）的用户 id，由 Java 端写入
--   code             临时验证码，由 Java 端写入；玩家在 KOOK 兑换成功后置 NULL
--   code_expires_at  验证码过期时间（unix 秒）。可留空，留空时 Python 端按
--                    created_at + bind_code_ttl（默认 900 秒）兜底判定
--   kook_id          兑换成功后写入的 KOOK 用户 id，Java 端靠它反查绑定关系
--   created_at       创建时间（unix 秒）
--   bound_at         绑定成功时间（unix 秒）
--
-- 「一对一」约束落在 ux_bindings_kook 这个部分唯一索引上。以后要放开成
-- 「一个 KOOK 绑多个游戏账号」，把这个索引删掉即可，其它逻辑不用动。

CREATE TABLE IF NOT EXISTS bindings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id     TEXT    NOT NULL,
    code            TEXT,
    code_expires_at INTEGER,
    kook_id         TEXT,
    created_at      INTEGER NOT NULL,
    bound_at        INTEGER
);

-- 验证码唯一（只约束「还有验证码」的行）
CREATE UNIQUE INDEX IF NOT EXISTS ux_bindings_code
    ON bindings(code) WHERE code IS NOT NULL;

-- 一个 KOOK 账号只能绑一次 —— 当前一对一约束的落点
CREATE UNIQUE INDEX IF NOT EXISTS ux_bindings_kook
    ON bindings(kook_id) WHERE kook_id IS NOT NULL;

-- 一个游戏账号在同一时间只保留一条绑定记录：
-- Java 端给已存在的玩家发码时要用 UPSERT，不要直接 INSERT（否则会撞这个索引）
CREATE UNIQUE INDEX IF NOT EXISTS ux_bindings_external
    ON bindings(external_id);

-- 绑定频道（每服务器一个），由管理员用 `/bind channel` 设置
CREATE TABLE IF NOT EXISTS bind_channels (
    guild_id   TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    updated_at INTEGER NOT NULL
);
