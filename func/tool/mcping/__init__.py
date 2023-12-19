from avilla.core import Context, MessageReceived
from avilla.twilight.twilight import (
    FullMatch,
    RegexResult,
    Twilight,
    WildcardMatch,
)
from graia.saya import Channel
from graiax.shortcut import dispatch, listen

from utils.message.preprocessor import MentionMe
from utils.saya import build_metadata
from utils.saya.model import FuncType, GroupData

from .crud import delete_bind, get_bind, set_bind
from .mcping import get_mcping

channel = Channel.current()
channel.meta = build_metadata(
    func_type=FuncType.tool,
    name="Minecraft服务器状态查询",
    version="1.0",
    description="查询Minecraft服务器状态",
    usage=[
        "发送指令：mcping [bind] <address>",
    ],
    options=[
        {"name": "bind", "help": "绑定服务器"},
        {"name": "address", "help": "服务器地址，可选"},
    ],
    example=[
        {"run": "mcping bind a60.one", "to": "在本群绑定服务器 a60.one"},
        {"run": "mcping a60.one", "to": "查询服务器 a60.one 的状态"},
        {"run": "mcping", "to": "查询本群绑定的服务器状态"},
    ],
)


@listen(MessageReceived)
@dispatch(
    Twilight(
        [
            FullMatch("mcping"),
            "arg_bind" @ FullMatch("bind", optional=True),
            "arg_address" @ WildcardMatch(optional=True),
        ],
        preprocessor=MentionMe(),
    )
)
async def main(
    ctx: Context,
    agroup: GroupData,
    arg_bind: RegexResult,
    arg_address: RegexResult,
):
    address = str(arg_address.result) if arg_address.result else str(await get_bind(agroup.group_id))
    if arg_bind.result and not arg_address.result and address:
        await delete_bind(agroup.group_id)
        await ctx.scene.send_message(f"服务器 {address} 解绑成功")
    elif arg_bind.result and not arg_address.result or not arg_bind.result and not address:
        await ctx.scene.send_message("本群未绑定服务器")
    elif arg_bind.result:
        await set_bind(agroup.group_id, address)
        await ctx.scene.send_message(f"服务器 {address} 绑定成功")
    else:
        ping_result = await get_mcping(address)
        await ctx.scene.send_message(ping_result)
