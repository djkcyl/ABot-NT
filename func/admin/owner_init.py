from typing import Annotated

import kayaku
from avilla.core import Context, MessageChain, MessageReceived
from avilla.twilight.twilight import FullMatch, ParamMatch, ResultValue, Twilight
from graia.amnesia.builtins.memcache import Memcache
from graia.saya import Channel
from graiax.shortcut import dispatch, listen

from models.saya import FuncType
from utils.config import BasicConfig
from utils.db import AUser
from utils.message.preprocessor import MentionMe
from utils.saya import build_metadata

channel = Channel.current()
channel.meta = build_metadata(
    func_type=FuncType.admin,
    name="所有者初始化",
    version="1.0",
    description="首次启动时，为所有者初始化一个随机密码，用来绑定所有者身份。",
    cmd_prefix="owner",
    can_be_disabled=False,
    hidden=True,
)
config = kayaku.create(BasicConfig)


@listen(MessageReceived)
@dispatch(Twilight([FullMatch("owner"), FullMatch("bind"), "arg_code" @ ParamMatch()], preprocessor=MentionMe()))
async def owner_init(ctx: Context, memcache: Memcache, auser: AUser, arg_code: Annotated[MessageChain, ResultValue()]):  # noqa: ANN201
    if str(arg_code) == await memcache.get("owner_init_code"):
        await memcache.delete("owner_init_code")
        config.owner = auser.aid
        kayaku.save(config)
        return await ctx.scene.send_message("Owner 绑定成功！")
