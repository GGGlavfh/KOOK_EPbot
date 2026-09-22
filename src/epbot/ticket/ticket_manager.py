"""工单核心业务逻辑

- `/ticket on`   在当前频道放出发票面板（卡片）
- `/ticket off`  关闭本服务器的工单入口
- 点击面板按钮   -> 建/复用「工单」分组，在里面建私密频道、只放行发起人、发送工单卡片
- 点击工单卡片上的「关闭工单」-> 删除频道，完成关票

面板频道与工单归属存在数据目录的 ticket_state.json，每次操作直接读写文件，不在内存里留存。
"""
import asyncio

from khl import Bot, Event, EventTypes, Message

from ..common import (CHANNEL_GONE, CHANNEL_OK, CHANNEL_UNKNOWN, channel_state, read_json,
                      write_json_atomic)
from ..paths import TICKET_CONFIG_PATH, TICKET_STATE_PATH
from .ticket_cards import CLOSE_VALUE, get_menu_card, get_ticket_card

USAGE = "用法：/ticket on 放出发票面板，/ticket off 关闭工单入口"

# KOOK 频道权限比特位
PERM_VIEW = 1 << 1  # 查看文字、语音频道
PERM_SEND = 1 << 2  # 发布消息
EVERYONE_ROLE_ID = 0  # @全体成员

# 状态的读-改-写要串起来，否则并发点击会互相覆盖，甚至写出半截 JSON
_LOCK = asyncio.Lock()


def _load_config() -> dict:
    config = read_json(TICKET_CONFIG_PATH)
    if config is None:
        print(f"[warn] 读取 {TICKET_CONFIG_PATH.name} 失败，按钮将为空")
        return {}
    return config


_CONFIG = _load_config()
# {按钮 value: 工单类型名}
TYPES = {item.get('value', ''): item.get('name', '') for item in _CONFIG.get('buttons', [])}


# 状态文件结构：
# {"guilds": {guild_id: {"menu_channel": channel_id, "category_id": category_id}},
#  "tickets": {channel_id: {"guild_id": ..., "user_id": ..., "type": ..., "name": ...}}}
def _read_state() -> dict:
    """每次都从文件读，保证文件是唯一数据源"""
    state = read_json(TICKET_STATE_PATH)
    if not isinstance(state, dict):
        state = {}
    state.setdefault('guilds', {})
    state.setdefault('tickets', {})
    return state


def _write_state(state: dict):
    """原子写：先写临时文件再替换，避免写出半截 JSON 导致记录全丢"""
    write_json_atomic(TICKET_STATE_PATH, state)


def _find_open_channel(state: dict, guild_id: str, user_id: str, type_value: str):
    """在状态里查该用户是否已经开过同类工单，返回频道 id 或 None"""
    for ticket_channel_id, info in state['tickets'].items():
        if not isinstance(info, dict):
            continue
        if (info.get('guild_id') == guild_id and info.get('user_id') == user_id
                and info.get('type') == type_value):
            return ticket_channel_id
    return None


async def _find_alive_ticket(bot: Bot, guild_id: str, user_id: str, type_value: str):
    """查该用户未关闭的同类工单，返回 `(频道 id 或 None, 状态)`

    只有**确认**频道已不在服务器频道清单里（`CHANNEL_GONE`）才清记录；
    `CHANNEL_UNKNOWN` 一律保留 —— 「读不到」不等于「已删除」，
    误删记录会让那张票的「关闭工单」按钮彻底失效。
    """
    async with _LOCK:
        channel_id = _find_open_channel(_read_state(), guild_id, user_id, type_value)

    if not channel_id:
        return None, CHANNEL_OK
    state = await channel_state(bot, guild_id, channel_id)
    if state == CHANNEL_OK:
        return channel_id, CHANNEL_OK
    if state == CHANNEL_GONE:
        # 频道确实没了，清掉记录，否则这个用户以后都开不了这种票
        async with _LOCK:
            current = _read_state()
            current['tickets'].pop(channel_id, None)
            _write_state(current)
        print(f"[info] 工单频道 {channel_id} 已不存在，已清除记录")
        return None, CHANNEL_GONE
    print(f"[warn] 工单频道 {channel_id} 状态无法确认，保留记录")
    return channel_id, CHANNEL_UNKNOWN


async def _notify_user(bot: Bot, channel_id: str, user_id: str, content: str):
    """只发给指定用户看的提示，不刷屏、也不会把面板卡片顶掉"""
    try:
        channel = await bot.client.fetch_public_channel(channel_id)
        await channel.send(content, temp_target_id=user_id)
    except Exception as e:
        print(f"[warn] 发送提示失败: {e}")


async def _discard_channel(bot: Bot, channel_id: str):
    """删掉刚建出来的频道，避免留下公开的孤儿频道"""
    try:
        await bot.client.delete_channel(channel_id)
    except Exception as e:
        print(f"[warn] 清理频道失败: {e}")


async def _set_private_permission(channel, user_id: str):
    """把频道设为私密：禁止 @全体成员查看，再单独放行工单发起人"""
    # 1. 禁止所有人查看（权限项不存在时先创建）
    try:
        await channel.create_role_permission(EVERYONE_ROLE_ID)
    except Exception:
        pass
    await channel.update_role_permission(EVERYONE_ROLE_ID, allow=0, deny=PERM_VIEW)

    # 2. 放行发起人（用户级权限优先于角色级）
    try:
        await channel.create_user_permission(user_id)
    except Exception:
        pass
    await channel.update_user_permission(user_id, allow=PERM_VIEW | PERM_SEND, deny=0)


async def _permission_applied(channel) -> bool:
    """回读一遍频道权限，确认「禁止所有人查看」真的生效了

    KOOK 的频道如果开了「同步分类权限」，频道级设置会被分类覆盖，
    这里读不到就说明没生效，需要提醒用户，别静默地把工单频道开成公开的。
    """
    try:
        perm = await channel.fetch_permission(force_update=True)
    except Exception:
        return True  # 读不到就不报警，避免误报
    return any(rp.role_id == EVERYONE_ROLE_ID and rp.deny & PERM_VIEW for rp in perm.roles)


async def _ensure_category_private(category):
    """让工单分组只对服主/管理员可见：@全体成员 禁止查看

    官方文档：在分组 id 上改权限会同步给所有 sync=1 的子频道，
    所以必须在建子频道之前调，否则会把子频道的用户级放行一起冲掉。
    """
    try:
        perm = await category.fetch_permission(force_update=True)
        if any(rp.role_id == EVERYONE_ROLE_ID and rp.deny & PERM_VIEW for rp in perm.roles):
            return  # 已经是私密的，不重复改
    except Exception:
        pass

    try:
        await category.create_role_permission(EVERYONE_ROLE_ID)
    except Exception:
        pass
    await category.update_role_permission(EVERYONE_ROLE_ID, allow=0, deny=PERM_VIEW)


async def _get_ticket_category(bot: Bot, guild_id: str, guild):
    """拿到工单分组：配置指定 > 上次建的 > 新建一个

    拿到后都会把分组设为私密（仅服主/管理员可见），再让工单频道挂在它下面。
    """
    explicit = _CONFIG.get('category_id')
    if explicit:
        category = await bot.client.fetch_channel_category(explicit)
        await _ensure_category_private(category)
        return category

    async with _LOCK:
        recorded = _read_state()['guilds'].get(guild_id, {}).get('category_id')

    if recorded:
        category = None
        try:
            category = await bot.client.fetch_channel_category(recorded)
        except Exception:
            category = None  # 分组被删了，下面重新建一个
        if category is not None:
            await _ensure_category_private(category)
            return category

    category = await guild.create_channel_category(_CONFIG.get('category_name', '工单'))
    await _ensure_category_private(category)

    async with _LOCK:
        state = _read_state()
        state['guilds'].setdefault(guild_id, {})['category_id'] = category.id
        _write_state(state)
    return category


async def _create_ticket(bot: Bot, guild_id: str, user_id: str, type_value: str,
                         type_name: str, menu_channel_id: str):
    """开票：同一用户在同一服务器、同一工单类型下只能有一个未关闭的频道"""
    # 1. 已经开过同类工单就只提示，不新建
    existing, state = await _find_alive_ticket(bot, guild_id, user_id, type_value)
    if existing:
        if state == CHANNEL_UNKNOWN:
            # 读不到记录里的频道：不能直接清（可能是权限/网络），把判断交给管理员
            await _notify_user(bot, menu_channel_id, user_id,
                               f"你已有一个 **{type_name}** 工单：(chn){existing}(chn)\n"
                               "⚠️ 但机器人暂时读不到那个频道（可能已被删除或权限变更）。"
                               "若确认它已不存在，请让管理员清理记录。")
        else:
            await _notify_user(bot, menu_channel_id, user_id,
                               f"你已经有一个 **{type_name}** 工单了：(chn){existing}(chn)")
        return

    # 2. 建分组 + 频道，再设为私密；任何一步出错都把频道删掉，不留公开的孤儿频道
    channel = None
    try:
        guild = await bot.client.fetch_guild(guild_id)
        category = await _get_ticket_category(bot, guild_id, guild)
        name = f"{_CONFIG.get('channel_prefix', '工单-')}{type_name}-{user_id}"
        channel = await guild.create_text_channel(name, category)
        await _set_private_permission(channel, user_id)
    except Exception as e:
        print(f"[warn] 创建工单频道失败: {e}")
        if channel is not None:
            await _discard_channel(bot, channel.id)
        await _notify_user(bot, menu_channel_id, user_id, "工单创建失败，请稍后再试或联系管理员。")
        return

    # 3. 记录归属；再查一次是为了挡住「双击并发生成两个频道」
    async with _LOCK:
        state = _read_state()
        duplicate = _find_open_channel(state, guild_id, user_id, type_value)
        if duplicate is None:
            state['tickets'][channel.id] = {
                'guild_id': guild_id,
                'user_id': user_id,
                'type': type_value,
                'name': type_name,
            }
            _write_state(state)

    if duplicate:
        await _discard_channel(bot, channel.id)
        await _notify_user(bot, menu_channel_id, user_id,
                           f"你已经有一个 **{type_name}** 工单了：(chn){duplicate}(chn)")
        return

    # 4. 发工单卡片
    content = f"(met){user_id}(met) 你的**{type_name}**工单已创建，请在这里描述具体情况。"
    try:
        await channel.send(get_ticket_card(content))
    except Exception as e:
        print(f"[warn] 发送工单卡片失败: {e}")

    # 5. 回读权限，没生效就提醒用户，别让人以为这里是私密的
    if not await _permission_applied(channel):
        print(f"[warn] 频道 {channel.id} 的私密权限未生效，请检查该分组的「同步分类权限」设置")
        await _notify_user(bot, channel.id, user_id,
                           "⚠️ 本频道的私密权限可能未生效，请不要发送敏感信息，并请联系管理员。")


async def _close_ticket(bot: Bot, channel_id: str, user_id: str, is_guild_admin) -> bool:
    """关票：工单发起人、服主、管理员都可以关；返回是否执行了关票"""
    async with _LOCK:
        info = _read_state()['tickets'].get(channel_id)
    if not isinstance(info, dict):
        # 记录已经没了（比如工单频道被管理员手删过）但按钮还在：给点击者一句解释，别让人干等
        await _notify_user(bot, channel_id, user_id, "这个工单已经没有记录了，可能已被处理过。")
        return False

    # 不是发起人的话，服主 / 管理员也可以代关；没权限则保持静默
    if info.get('user_id') != user_id and not await is_guild_admin(info.get('guild_id'), user_id):
        return False

    # 先摘记录再删频道：频道可能已经被管理员手删过（delete 会报错），
    # 先删频道的话这里就会抛异常、记录留着，把用户的名额永久占住
    async with _LOCK:
        state = _read_state()
        state['tickets'].pop(channel_id, None)
        _write_state(state)

    try:
        await bot.client.delete_channel(channel_id)
    except Exception as e:
        print(f"[warn] 删除工单频道失败（记录已清除，不影响用户再开票）: {e}")
    return True


def setup(bot: Bot, admin_only: dict, is_guild_admin):
    """注册 ticket 指令与按钮点击事件

    admin_only 由 main.py 传入，保证指令仅管理员可用；
    is_guild_admin(guild_id, user_id) 用于判断点关票按钮的人是不是服主/管理员。
    """

    @bot.command(name="ticket", desc="开关本服务器的工单面板", **admin_only)
    async def ticket_cmd(msg: Message, action: str = ""):
        guild_id = msg.ctx.guild.id
        channel_id = msg.ctx.channel.id
        action = action.strip().lower()

        if action == "on":
            async with _LOCK:
                state = _read_state()
                state['guilds'].setdefault(guild_id, {})['menu_channel'] = channel_id
                _write_state(state)
            await msg.reply(get_menu_card())
        elif action == "off":
            async with _LOCK:
                state = _read_state()
                removed = state['guilds'].get(guild_id, {}).pop('menu_channel', None) is not None
                if removed:
                    _write_state(state)
            if removed:
                await msg.reply("已关闭本服务器的工单入口，之前发出的面板将不再响应。")
            else:
                await msg.reply("本服务器还没有开启工单面板。")
        else:
            await msg.reply(USAGE)

    @bot.on_event(EventTypes.MESSAGE_BTN_CLICK)
    async def on_btn_click(_bot: Bot, event: Event):
        body = event.body or {}
        value = body.get('value', '')
        user_id = body.get('user_id') or event.author_id
        guild_id = body.get('guild_id') or event.target_id
        channel_id = body.get('channel_id') or body.get('target_id')

        if value == CLOSE_VALUE:
            try:
                await _close_ticket(bot, channel_id, user_id, is_guild_admin)
            except Exception as e:
                print(f"[warn] 关闭工单失败: {e}")
            return

        type_name = TYPES.get(value)
        if not type_name:
            return

        # 只在开启了工单面板的频道里响应
        async with _LOCK:
            menu_channel = _read_state()['guilds'].get(guild_id, {}).get('menu_channel')
        if menu_channel != channel_id:
            return

        try:
            await _create_ticket(bot, guild_id, user_id, value, type_name, channel_id)
        except Exception as e:
            print(f"[warn] 创建工单失败: {e}")
