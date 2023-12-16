from arclet.alconna import Alconna, CommandMeta
from arclet.alconna.graia import AlconnaDispatcher
from avilla.core import Context, MessageReceived
from graia.saya import Channel
from graiax.shortcut.saya import dispatch, listen

from utils.saya import build_metadata
from utils.saya.model import FuncType

channel = Channel.current()
channel.meta = build_metadata(
    func_type=FuncType.tool,
    name="Hello World",
    version="1.0",
    description="Hello World",
    usage=["发送指令：/hello"],
)


@listen(MessageReceived)
@dispatch(
    AlconnaDispatcher(
        Alconna(
            "/hello",
            meta=CommandMeta(  # 仅 Meta，无实际功能，可在别的地方调用
                description="Hello World",
                usage="@bot /hello",
                example="@bot /hello",
                author="djkcyl",
            ),
        ),
        need_tome=True,
        remove_tome=True,
    )
)
async def main(ctx: Context, event: MessageReceived):
    await ctx.scene.send_message(str(event.message.content))
