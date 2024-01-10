from typing import Annotated

from avilla.core import Context, MessageChain, MessageReceived, Notice, Text
from avilla.twilight.twilight import (
    ArgResult,
    ArgumentMatch,
    ParamMatch,
    ResultValue,
    Twilight,
    UnionMatch,
)
from graia.saya import Channel
from graiax.shortcut import FunctionWaiter, dispatch, listen

from models.saya import FuncType
from utils.builder import AUserBuilder
from utils.db import AUser, GroupData
from utils.message.preprocessor import MentionMe
from utils.saya import build_metadata

channel = Channel.current()
channel.meta = build_metadata(
    func_type=FuncType.user,
    name="转账",
    version="1.2",
    description="转移游戏币给其他人",
    cmd_prefix="transfer",
    usage=["发送指令：transfer <At / aid> <数量> [-a, --all]"],
    options=[
        {
            "name": "At / aid",
            "help": "要转账的对象，请使用群内的 At 功能或输入目标用户的 aid，必选",
        },
        {"name": "数量", "help": "要转账的数量，和 `--all` 二选一，必选"},
        {"name": "-a, --all", "help": "是否转账所有可用的数量，和 `数量` 二选一，可选"},
    ],
    example=[
        {"run": "transfer @xxx 1", "to": "转账1个游戏币给 xxx"},
        {"run": "transfer @xxx --all", "to": "转账所有可用的游戏币给 xxx"},
    ],
    tips=[
        "由于 ABot 在群收不到 At，请在群内使用时，使用目标用户 aid 来转账（可以使用 `/mydata` 来检查自己的 aid）",
        "转账的数量不能超过每日限额（200）",
    ],
    can_be_disabled=False,
)


@listen(MessageReceived)
@dispatch(
    Twilight(
        [
            UnionMatch("transfer", "转账"),
            "arg_target" @ ParamMatch(optional=True),
            "arg_all" @ ArgumentMatch("-a", "--all", action="store_true"),
            "arg_num" @ ParamMatch(optional=True),
        ],
        preprocessor=MentionMe(),
    ),
)
async def main(  # noqa: ANN201
    ctx: Context,
    group_data: GroupData,
    auser: AUser,
    arg_target: Annotated[MessageChain, ResultValue()],
    arg_all: ArgResult,
    arg_num: Annotated[MessageChain, ResultValue()],
):
    if not arg_target:
        return await ctx.scene.send_message("未 At 指定要转账的对象或未指定目标的 aid")

    frist_element = arg_target[0]
    mentioned_user, mentioned_type = (
        (frist_element.target.last_value, "cid") if isinstance(frist_element, Notice) else (str(frist_element), "aid")
    )
    try:
        recipient_user = await AUserBuilder.get_user(mentioned_user, mentioned_type)
    except ValueError:
        return await ctx.scene.send_message("无法识别的用户类型")
    if recipient_user is None:
        err_msg = "，可能该用户未初始化" if mentioned_type == "cid" else "，可能输入的 aid 有误"
        return await ctx.scene.send_message(f"未找到指定的用户{err_msg}")

    if recipient_user.cid == auser.cid:
        return await ctx.scene.send_message("不能转账给自己")

    if len(str(arg_num)) > 6:
        return await ctx.scene.send_message("转账数字长度过长")

    if arg_all.result:
        num = auser.coin
    elif arg_num:
        try:
            num = abs(int(str(arg_num).strip()))
        except ValueError:
            return await ctx.scene.send_message("输入的内容不为整数")
    else:
        return await ctx.scene.send_message("未输入要转账的数量")

    if num <= 0:
        return await ctx.scene.send_message("转账数量必须大于 0")

    if num != int(str(arg_num).strip()):
        await auser.reduce_coin(num, force=True, group_id=group_data.group_id, source="罚款", detail="非法转账负数")
        return await ctx.scene.send_message(f"由于你试图转账负数，系统自动将扣除你 {num} 个游戏币")

    if num > auser.coin:
        return await ctx.scene.send_message("你没有足够的游戏币")

    if auser.today_transferred + num > 200:
        return await ctx.scene.send_message(
            f"需要转账的数量已超过今日限额，今日还可以转账 {200 - auser.today_transferred} 个游戏币"
        )

    await ctx.scene.send_message(f"正在转账 {num} 个游戏币给 AID：{recipient_user.aid}，请发送 `@ABot y` 确认转账")

    async def waiter(waiter_ctx: Context, message: MessageChain) -> bool | None:
        if waiter_ctx.client != ctx.client:
            return None
        message_str = str(message.get_first(Text)).removeprefix("/").strip().lower()
        if message_str in {"y", "yes", "是"}:
            return True
        if message_str in {"n", "no", "否"}:
            return False
        await waiter_ctx.scene.send_message("无效输入: 请重新确认")
        return None

    if not await FunctionWaiter(
        waiter,
        [MessageReceived],
        block_propagation=ctx.client.follows("::friend") or ctx.client.follows("::guild.user"),
    ).wait(30, False):
        return await ctx.scene.send_message("转账已取消")

    await auser.reduce_coin(
        num, group_id=group_data.group_id, source="转账", detail=f"转账给 AID：{recipient_user.aid}"
    )
    await recipient_user.add_coin(num, group_id=group_data.group_id, source="转账", detail=f"来自 AID：{auser.aid}")
    auser.today_transferred += num
    await auser.save()  # type: ignore

    return await ctx.scene.send_message(f"已经成功给 AID：{recipient_user.aid} 转账 {num} 个游戏币")
