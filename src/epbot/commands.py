"""指令的准入与异常处理

khl.py 的 `@bot.command` 支持 `rules`（准入规则）与 `exc_handlers`（异常处理），
这里把两者集中起来，用 `ADMIN_ONLY` 一次展开给所有管理员专属指令。
"""
from khl import Message, command
from khl.command import Exceptions

from .admin import is_admin

# 各指令的用法提示，参数个数不对时回给用户（新增指令记得在这里补一行）
COMMAND_USAGE = {
    'help': '/help',
    'welcome': '/welcome on | /welcome off',
    'ticket': '/ticket on | /ticket off',
    'bind': '/bind <验证码>（在绑定频道）｜管理员：/bind channel、/bind off',
}


async def admin_rule(msg: Message) -> bool:
    """命令规则：只有管理员才能通过校验"""
    return await is_admin(msg)


async def on_rule_not_passed(cmd: command.Command, exception: Exception, msg: Message):
    """非管理员触发指令：不做任何响应（挂上此处理器可避免异常被打印）"""
    pass


async def on_arg_len_not_matched(cmd: command.Command,
                                 exception: Exceptions.Handler.ArgLenNotMatched,
                                 msg: Message):
    """指令参数个数不对：给用户一句提示

    命令不响应容易被误认为机器人已下线，所以这里要给出反馈。
    规则校验在参数校验之前，能走到这里的必然是管理员。
    """
    if exception.actual < exception.expected_min:
        detail = "参数太少"
    elif exception.expected_max != -1 and exception.actual > exception.expected_max:
        detail = "参数太多"
    else:
        detail = "参数个数不对"
    usage = COMMAND_USAGE.get(cmd.name, f"/{cmd.name}")
    await msg.reply(f"{detail}，用法：{usage}")


# 管理员专属指令的公共参数，注册时用 **ADMIN_ONLY 展开
ADMIN_ONLY = dict(
    rules=[admin_rule],
    exc_handlers={
        Exceptions.Handler.RuleNotPassed: on_rule_not_passed,
        Exceptions.Handler.ArgLenNotMatched: on_arg_len_not_matched,
    },
)

# 普通成员可用的指令：只挂参数错误的提示，**不做**管理员准入（要不要权限由指令自己判断），
# 所以这里没有 rules —— 非管理员的指令必须能被响应，不能像 ADMIN_ONLY 那样静默吞掉
PUBLIC_ONLY = dict(
    exc_handlers={Exceptions.Handler.ArgLenNotMatched: on_arg_len_not_matched},
)
