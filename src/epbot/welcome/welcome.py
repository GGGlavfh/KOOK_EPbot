"""欢迎功能

管理员在目标频道发送 `/welcome on` 开启该频道的自动欢迎，`/welcome off` 关闭。
一个服务器同时只能有一个频道开启，开启记录保存在数据目录的 welcome_channels.json。

欢迎语从 WELCOME_MESSAGES 中随机抽取，采用「洗牌袋」策略：
一轮内每条都出现过之后才会重新洗牌，因此不会出现某条还没轮到就被重复抽中的情况。
模板中 {guild_name} 会替换为服务器名，(met)(met) 会替换为 at 新成员的语法。
"""
import random

from khl import Bot, Event, EventTypes, Message

from ..common import (CHANNEL_GONE, CHANNEL_OK, CHANNEL_UNKNOWN, channel_state, read_json,
                      write_json_atomic)
from ..paths import WELCOME_STATE_PATH

USAGE = "用法：/welcome on 开启自动欢迎，/welcome off 关闭"

WELCOME_MESSAGES = [
    "欢迎 (met)(met) 加入{guild_name}",
    "新成员 (met)(met) 加入了 {guild_name}，大家欢迎！",
    "(met)(met) 来到了 {guild_name}，快和大家打个招呼吧！",
    "(met)(met) 欢迎来到 {guild_name}，祝你玩得开心！",
    "(met)(met) 降落到了 {guild_name}，快找个位置坐下吧！",
    "(met)(met) 加入了 {guild_name} 大家庭，大家快来冒泡啦！",
]

# {guild_id: channel_id}
_targets = {}
# {guild_id: [本轮还没抽到的欢迎语下标]}
_bags = {}
# {guild_id: 上一次抽到的下标}，用于避免跨轮次连续重复
_last = {}
# {guild_id: 服务器名}
_guild_names = {}


def _load():
    global _targets
    _targets = read_json(WELCOME_STATE_PATH, {})


def _save():
    write_json_atomic(WELCOME_STATE_PATH, _targets)


async def _channel_name(bot: Bot, channel_id: str) -> str:
    """取频道名，取不到就退回频道 ID"""
    try:
        return (await bot.client.fetch_public_channel(channel_id)).name
    except Exception:
        return channel_id


async def _guild_name(bot: Bot, guild_id: str) -> str:
    """取服务器名（缓存），取不到就退回兜底文案

    只在取到名字时才写缓存：失败（网络抖动、权限不足等）不缓存，
    否则一次失败就会把服务器名永久固定成兜底文案。
    """
    cached = _guild_names.get(guild_id)
    if cached:
        return cached
    try:
        name = (await bot.client.fetch_guild(guild_id)).name
    except Exception:
        return '本服务器'
    if name:
        _guild_names[guild_id] = name
    return name or '本服务器'


def _next_message(guild_id: str) -> str:
    """随机取一条欢迎语：本轮抽完（每条都出现过）才重新洗牌"""
    bag = _bags.get(guild_id)
    if not bag:
        bag = list(range(len(WELCOME_MESSAGES)))
        random.shuffle(bag)
        # 避免新一轮的第一条和上一轮最后一条重屴（袋尾先被 pop）
        if len(bag) > 1 and bag[-1] == _last.get(guild_id):
            bag[-1], bag[-2] = bag[-2], bag[-1]
        _bags[guild_id] = bag
    index = bag.pop()
    _last[guild_id] = index
    return WELCOME_MESSAGES[index]


def _forget(guild_id: str):
    """清掉某服务器的开启记录并落盘"""
    if _targets.pop(guild_id, None) is not None:
        _save()


def setup(bot: Bot, admin_only: dict):
    """注册 welcome 指令与入服事件；admin_only 由 main.py 传入，保证仅管理员可用"""
    _load()

    @bot.command(name="welcome", desc="开关本频道的自动欢迎", **admin_only)
    async def welcome_cmd(msg: Message, action: str = ""):
        guild_id = msg.ctx.guild.id
        channel_id = msg.ctx.channel.id
        enabled = _targets.get(guild_id)
        action = action.strip().lower()

        if action == "on":
            if enabled == channel_id:
                await msg.reply("本频道的自动欢迎已经是开启状态。")
            elif enabled:
                state = await channel_state(bot, guild_id, enabled)
                if state == CHANNEL_OK:
                    name = await _channel_name(bot, enabled)
                    await msg.reply(f"本服务器已在 #{name} 开启自动欢迎，请先在该频道发送 /welcome off 关闭。")
                elif state == CHANNEL_GONE:
                    _targets[guild_id] = channel_id
                    _save()
                    await msg.reply("原来开启自动欢迎的频道已被删除，已清理旧记录，并在本频道开启。")
                else:
                    # 读不到旧频道（权限变更/网络问题）：旧绑定对机器人已不可用，接管但要说清楚
                    _targets[guild_id] = channel_id
                    _save()
                    await msg.reply("⚠️ 原频道读取失败（可能已被删除或机器人权限不足），"
                                    "已改到本频道开启。若原频道其实还在，请检查机器人在那里的权限。")
            else:
                _targets[guild_id] = channel_id
                _save()
                await msg.reply("已开启本频道的自动欢迎，新成员加入时会在这里收到欢迎消息。")
        elif action == "off":
            if enabled == channel_id:
                _targets.pop(guild_id)
                _save()
                await msg.reply("已关闭本频道的自动欢迎。")
            elif enabled:
                state = await channel_state(bot, guild_id, enabled)
                if state == CHANNEL_GONE:
                    # 旧频道确实没了，顺手清理，否则这个服务器再也开不了自动欢迎
                    _forget(guild_id)
                    await msg.reply("原来开启自动欢迎的频道已被删除，已清理旧记录。"
                                    "现在可以在本频道用 /welcome on 开启。")
                elif state == CHANNEL_UNKNOWN:
                    # 分不清就别乱删，宁可让管理员稍后再试
                    await msg.reply("本频道没有开启自动欢迎；原频道暂时读取失败，"
                                    "为免误删记录这里不动它，请稍后再试。")
                else:
                    name = await _channel_name(bot, enabled)
                    await msg.reply(f"本频道没有开启自动欢迎。本服务器目前在 #{name} 开启，"
                                    "请到那个频道发送 /welcome off。")
            else:
                await msg.reply("本频道没有开启自动欢迎。")
        else:
            await msg.reply(USAGE)

    @bot.on_event(EventTypes.JOINED_GUILD)
    async def on_joined_guild(_bot: Bot, event: Event):
        body = event.body or {}
        guild_id = body.get('guild_id') or event.target_id
        user_id = body.get('user_id') or event.author_id

        channel_id = _targets.get(guild_id)
        if not channel_id:
            return
        try:
            channel = await bot.client.fetch_public_channel(channel_id)
        except Exception as e:
            print(f"[warn] 发送欢迎消息失败: {e}")
            # 读不到不等于已删除：确认真的没了才清记录，否则保留
            state = await channel_state(bot, guild_id, channel_id)
            if state == CHANNEL_GONE:
                _forget(guild_id)
                print(f"[info] 服务器 {guild_id} 的欢迎频道 {channel_id} 已不存在，已清除开启记录")
            elif state == CHANNEL_UNKNOWN:
                print(f"[warn] 欢迎频道 {channel_id} 状态无法确认，保留开启记录")
            return
        try:
            content = _next_message(guild_id)
            content = content.replace('(met)(met)', f'(met){user_id}(met)')
            await channel.send(content.format(guild_name=await _guild_name(bot, guild_id)))
        except Exception as e:
            print(f"[warn] 发送欢迎消息失败: {e}")
