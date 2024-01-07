import re
from typing import Annotated

from avilla.core import Context, MessageChain, MessageReceived, Text
from avilla.twilight.twilight import RegexMatch, ResultValue, Twilight, WildcardMatch
from graia.saya import Channel
from graiax.shortcut import dispatch, listen

from models.saya import FuncType
from utils.db import AUser
from utils.message.preprocessor import MentionMe
from utils.saya import build_metadata
from utils.tencentcloud import tcc

channel = Channel.current()
channel.meta = build_metadata(
    func_type=FuncType.user,
    name="昵称",
    version="1.0",
    cmd_prefix="nickname",
    description="设置 ABot 称呼你时的昵称",
    usage=["发送指令：nickname <昵称>"],
    example=[{"run": "@ABot nickname 你好", "to": "设置昵称为“你好”"}],
    can_be_disabled=False,
)


@listen(MessageReceived)
@dispatch(
    Twilight(
        [RegexMatch(r"nickname|(修改|设(定|置))(昵称|别名)"), "arg_nickname" @ WildcardMatch(optional=True)],
        preprocessor=MentionMe(),
    )
)
async def main(ctx: Context, auser: AUser, arg_nickname: Annotated[MessageChain, ResultValue()]):  # noqa: ANN201
    if not arg_nickname:
        return await ctx.scene.send_message(
            "你还没有设置昵称哦"
            if not auser.nickname
            else f"你的昵称是：{auser.nickname}，要修改的话请发送：@ABot nickname <昵称>"
        )

    nickname = str(arg_nickname.get_first(Text)).strip()
    if len(nickname) > 12:
        return await ctx.scene.send_message("昵称太长了，最多 12 个字哦")
    if len(nickname) < 3:
        return await ctx.scene.send_message("昵称太短了，最少 3 个字哦")
    if nickname.isdigit():
        return await ctx.scene.send_message("昵称不可以是全数字哦")
    if nickname.isspace():
        return await ctx.scene.send_message("昵称不可以是空白哦")
    if not re.match(r"^[\u4e00-\u9fa5A-Za-z0-9_\u3040-\u309F\u30A0-\u30FF]+$", nickname):
        return await ctx.scene.send_message("昵称只能包含中文、英文、数字和下划线哦")

    if nickname == auser.nickname:
        return await ctx.scene.send_message("你的昵称已经是这个了哦")

    moderation = await tcc.text_moderation(nickname)
    if not moderation.is_safe:
        return await ctx.scene.send_message("昵称中含有敏感词，请修改后重试")

    await auser.set_nickname(nickname)
    return await ctx.scene.send_message(f"你的昵称已设置为：{nickname}")
