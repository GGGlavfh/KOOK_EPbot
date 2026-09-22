"""装配与启动

`register()` 注册指令与事件处理器，`run()` 再启动机器人。把两者分开是为了让
「导入本模块」不产生副作用（重复注册会因指令名冲突而报错），方便测试和复用。
"""
import asyncio

from khl import Message

from .admin import is_admin, is_guild_admin
from .bind.bind_manager import setup as setup_bind
from .bot import bot
from .commands import ADMIN_ONLY, PUBLIC_ONLY
from .paths import ensure_data_dir
from .ticket.ticket_manager import setup as setup_ticket
from .welcome.welcome import setup as setup_welcome

HELP_TEXT = (
    "你好，我是EPbot，以下是我的指令列表：\n"
    "/help - 显示帮助信息\n"
    "/welcome on/off - 开关欢迎功能\n"
    "/ticket on/off - 开关工单功能\n"
    "/bind <验证码> - 绑定游戏账号（在绑定频道，所有成员可用）\n"
    "/bind channel / off - 设置或关闭绑定频道（管理员）\n"
)


def register():
    """注册全部指令与事件处理器

    只应调用一次：khl.py 的 CommandManager 遇到同名指令会直接抛错。
    """
    ensure_data_dir()

    @bot.command(name="help", desc="帮助", **ADMIN_ONLY)
    async def help_command(msg: Message):
        await msg.reply(HELP_TEXT)

    # 欢迎功能（epbot/welcome/welcome.py）
    setup_welcome(bot, ADMIN_ONLY)

    # 工单功能（epbot/ticket/ticket_manager.py）
    setup_ticket(bot, ADMIN_ONLY, is_guild_admin)

    # 跨平台绑定（epbot/bind/bind_manager.py）
    # 注意传的是 PUBLIC_ONLY：/bind 对普通成员开放，管理员校验在指令内部单独做
    setup_bind(bot, PUBLIC_ONLY, is_admin)


def run():
    """注册并启动机器人（阻塞）"""
    register()
    print("机器人正在连接 KOOK...")
    # Python 3.10+ 不再隐式创建事件循环，khl.py 的 bot.run() 依赖 get_event_loop()
    asyncio.set_event_loop(asyncio.new_event_loop())
    bot.run()
