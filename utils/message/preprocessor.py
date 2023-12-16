from avilla.core import MessageReceived
from avilla.core.elements import Notice, Text
from avilla.standard.core.profile.metadata import Nick
from avilla.twilight.base import ChainDecorator
from graia.amnesia.message import Element
from graia.amnesia.message.chain import MessageChain
from graia.broadcast.interfaces.dispatcher import DispatcherInterface


class MentionMe(ChainDecorator):
    """At 账号或者提到账号群昵称，如果有则提取，没有则不提取"""

    def __init__(self, name: bool | str = True) -> None:
        """
        Args:
            name (Union[bool, str]): 是否提取昵称, 如果为 True, 则自动提取昵称, \
            如果为 False 则禁用昵称, 为 str 则将参数作为昵称
        """
        self.name = name

    async def __call__(self, chain: MessageChain, interface: DispatcherInterface) -> MessageChain:
        if not isinstance(interface.event, MessageReceived):
            return chain
        ctx = interface.event.context
        name: str | None = self.name if isinstance(self.name, str) else None
        # if self.name is True:
        #     name = (await ctx[ctx.self].pull(Nick)).nickname  # 将来换成 ctx.self.pull(Nick)
        first: Element = chain[0]
        if isinstance(name, str) and isinstance(first, Text) and str(first).startswith(name):
            return chain.removeprefix(name).removeprefix(" ")
        if isinstance(first, Notice) and first.target.last_value == ctx.self.last_value:
            mc = MessageChain(chain.content[1:])
            if mc.has(Text):
                return mc.removeprefix(" ")
        return chain
