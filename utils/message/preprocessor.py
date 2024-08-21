from typing import TYPE_CHECKING

from avilla.core import MessageReceived
from avilla.core.elements import Notice, Text
from avilla.twilight.base import ChainDecorator
from graia.amnesia.message.chain import MessageChain
from graia.broadcast.interfaces.dispatcher import DispatcherInterface

if TYPE_CHECKING:
    from graia.amnesia.message import Element


class MentionMe(ChainDecorator):
    """从消息链中去除 Notice 和消息首尾的空格和斜杠"""

    async def __call__(self, chain: MessageChain, interface: DispatcherInterface) -> MessageChain:
        if not isinstance(interface.event, MessageReceived):
            return chain
        ctx = interface.event.context
        first: Element = chain[0]
        if isinstance(first, Notice) and (first.target.last_value in (ctx.self.last_value, "2854214511")):
            chain = MessageChain(chain.content[1:])
        if chain.has(Text):
            return chain.strip(" ").removeprefix("/").strip(" ")
        return chain
