"""跨平台绑定业务（KOOK 侧）

两端协作流程：

1. **Java 端**（游戏服）生成验证码，连同自己的用户 id 写进共享的 SQLite（表结构见 `schema.sql`）
2. **玩家**在 KOOK 的绑定频道发送 `/bind <验证码>`
3. 这里校验验证码 → 清掉验证码 → 把玩家的 KOOK id 写进同一条记录

> `/bind` 是**普通成员也能用**的指令，和项目里其它管理员专属指令不同，所以注册时**不能**套 `ADMIN_ONLY`；
> 只有 `channel` / `off` 两个子命令在函数内部单独查管理员。

指令一览：

| 指令 | 谁能用 | 说明 |
| --- | --- | --- |
| `/bind <验证码>` | 任何成员 | 仅限已设置的绑定频道 |
| `/bind channel` | 管理员 | 把当前频道设为绑定频道 |
| `/bind off` | 管理员 | 关闭本服务器的绑定功能 |

所有回复都通过 `temp_target_id` 只发给发起者本人，不在频道里刷屏。
"""
from khl import Bot, Message

from ..config import BIND_CODE_TTL
from . import bind_db

USAGE = ("用法：/bind <验证码>（在绑定频道里发）\n"
         "管理员：/bind channel 把本频道设为绑定频道，/bind off 关闭绑定功能")

# 子命令（这两个要管理员权限，其余参数一律当验证码处理）
SUBCOMMANDS = ('channel', 'off')


async def _reply_temp(bot: Bot, channel_id: str, user_id: str, content: str):
    """只发给发起者本人看的回复，避免在频道里刷屏"""
    try:
        channel = await bot.client.fetch_public_channel(channel_id)
        await channel.send(content, temp_target_id=user_id)
    except Exception as e:
        print(f"[warn] 发送绑定提示失败: {e}")


def setup(bot: Bot, public_opts: dict, is_admin):
    """注册 /bind 指令

    public_opts 由 main.py 传入（只有参数错误的提示，没有管理员准入规则）；
    is_admin(msg) 用于判断子命令的权限 —— `/bind` 本身对所有人开放。
    """
    bind_db.init_schema()

    @bot.command(name="bind", desc="绑定游戏账号", **public_opts)
    async def bind_cmd(msg: Message, code: str = ""):
        guild = getattr(msg.ctx, 'guild', None)
        if guild is None:  # 私聊拿不到服务器信息，也就没有「绑定频道」的概念
            return
        guild_id = guild.id
        channel_id = msg.ctx.channel.id
        user_id = str(msg.author_id)
        arg = (code or '').strip()

        # ---- 子命令：设置 / 关闭绑定频道（管理员） ----
        if arg.lower() in SUBCOMMANDS:
            if not await is_admin(msg):
                await _reply_temp(bot, channel_id, user_id, "这个子命令只有管理员可以用。")
                return
            if arg.lower() == 'channel':
                bind_db.set_bind_channel(guild_id, channel_id)
                await _reply_temp(bot, channel_id, user_id,
                                  "已把本频道设为绑定频道。成员在游戏内获取验证码后，"
                                  "在这里发送 `/bind <验证码>` 即可完成绑定。")
            else:
                removed = bind_db.clear_bind_channel(guild_id)
                await _reply_temp(bot, channel_id, user_id,
                                  "已关闭本服务器的绑定功能。" if removed else "本服务器还没有设置绑定频道。")
            return

        # ---- 普通成员绑定 ----
        if not arg:
            await _reply_temp(bot, channel_id, user_id, USAGE)
            return

        bind_channel = bind_db.get_bind_channel(guild_id)
        if not bind_channel:
            return  # 没开启绑定功能，保持静默（和 /welcome、/ticket 未开启时的行为一致）
        if bind_channel != channel_id:
            await _reply_temp(bot, channel_id, user_id,
                              f"请到 <#{bind_channel}> 去绑定。")
            return

        status, external_id = bind_db.claim(arg, user_id, BIND_CODE_TTL)
        if status == bind_db.OK:
            await _reply_temp(bot, channel_id, user_id,
                              f"绑定成功！你的 KOOK 账号已与游戏账号 `{external_id}` 绑定。")
        elif status == bind_db.ALREADY_BOUND:
            extra = f"（已绑定：`{external_id}`）" if external_id else ""
            await _reply_temp(bot, channel_id, user_id,
                              f"你在这个服务器已经绑定过游戏账号了{extra}。目前不支持重复绑定，"
                              "如需改绑请联系管理员。")
        elif status == bind_db.EXPIRED:
            await _reply_temp(bot, channel_id, user_id,
                              "验证码已过期，请在游戏内重新获取。")
        elif status == bind_db.TAKEN:
            await _reply_temp(bot, channel_id, user_id,
                              "这个验证码刚刚被用掉了，请在游戏内重新获取。")
        else:  # NOT_FOUND
            await _reply_temp(bot, channel_id, user_id,
                              "验证码不正确，或者已经被使用过了。请在游戏内重新获取。")
