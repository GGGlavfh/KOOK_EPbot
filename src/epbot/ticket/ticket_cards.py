"""工单卡片生成

只负责把卡片拼出来，不含任何业务逻辑。
对外暴露两个函数：`get_menu_card()`（开票面板）和 `get_ticket_card(content)`（开票后的卡片）。
按钮的名字与 value 暗号来自同目录的 ticket_config.json。
"""
from khl.card import Card, CardMessage, Element, Module, Types

from ..common import read_json
from ..paths import TICKET_CONFIG_PATH

# 「关闭工单」按钮的 value，ticket_manager 靠它识别关票操作
CLOSE_VALUE = 'ticket_close'


def _load_config() -> dict:
    config = read_json(TICKET_CONFIG_PATH)
    if config is None:
        print(f"[warn] 读取 {TICKET_CONFIG_PATH.name} 失败，按钮将为空")
        return {}
    return config


_CONFIG = _load_config()


def get_menu_card() -> CardMessage:
    """开票面板：一行工单类型按钮"""
    buttons = [
        Element.Button(
            item.get('name', ''),
            value=item.get('value', ''),
            click=Types.Click.RETURN_VAL,
            theme=Types.Theme.PRIMARY,
        )
        for item in _CONFIG.get('buttons', [])
    ]
    card = Card(
        Module.Header(_CONFIG.get('menu_title', '工单')),
        Module.Section(_CONFIG.get('menu_text', '')),
        Module.ActionGroup(*buttons),
    )
    return CardMessage(card)


def get_ticket_card(content: str) -> CardMessage:
    """开票后的卡片，带一个「关闭工单」按钮"""
    card = Card(
        Module.Header(_CONFIG.get('ticket_title', '工单已创建')),
        Module.Section(content),
        Module.ActionGroup(
            Element.Button(
                _CONFIG.get('close_button', '关闭工单'),
                value=CLOSE_VALUE,
                click=Types.Click.RETURN_VAL,
                theme=Types.Theme.DANGER,
            )
        ),
    )
    return CardMessage(card)
