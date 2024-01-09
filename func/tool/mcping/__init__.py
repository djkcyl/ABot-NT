from avilla.core import Context, MessageReceived
from avilla.twilight.twilight import (
    FullMatch,
    RegexResult,
    Twilight,
    WildcardMatch,
)
from graia.saya import Channel
from graiax.shortcut import dispatch, listen

from models.saya import FuncType
from utils.db import GroupData
from utils.message.preprocessor import MentionMe
from utils.saya import build_metadata

from .crud import delete_bind, get_bind, set_bind
from .mcping import get_mcping

channel = Channel.current()
channel.meta = build_metadata(
    func_type=FuncType.tool,
    name="Minecraft服务器状态查询",
    version="1.1",
    description="查询Minecraft服务器状态",
    cmd_prefix="mcping",
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
async def main(  # noqa: ANN201
    ctx: Context,
    agroup: GroupData,
    arg_bind: RegexResult,
    arg_address: RegexResult,
):
    if arg_bind.result:
        if str(arg_address.result):
            # 请求绑定且提供了新的地址
            await set_bind(agroup.group_id, str(arg_address.result))
            await ctx.scene.send_message("服务器绑定成功")
        elif await get_bind(agroup.group_id):
            await delete_bind(agroup.group_id)
            await ctx.scene.send_message("服务器解绑成功")
        else:
            await ctx.scene.send_message("本群未绑定服务器，且未提供新的地址，无法解绑或绑定服务器")
    else:
        address = str(arg_address.result) if arg_address.result else await get_bind(agroup.group_id)
        if address:
            # 没有绑定请求但存在已绑定地址，执行 ping 操作
            await ctx.scene.send_message("正在查询服务器状态，请稍后...")
            ping_result = await get_mcping(address)
            await ctx.scene.send_message(ping_result)
        else:
            # 没有绑定请求也没有地址，发送未绑定信息
            await ctx.scene.send_message("本群未绑定服务器，或未指定服务器地址")
