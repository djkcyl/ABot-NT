import re
from io import BytesIO
from typing import Annotated

from avilla.core import Context, MessageChain, MessageReceived, Picture, Text
from avilla.twilight.twilight import (
    ArgResult,
    ArgumentMatch,
    FullMatch,
    ParamMatch,
    RegexMatch,
    ResultValue,
    Twilight,
    UnionMatch,
    WildcardMatch,
)
from graia.saya import Channel
from graiax.shortcut import FunctionWaiter, dispatch, listen
from loguru import logger
from PIL import Image
from pyzbar import pyzbar

from models.saya import FuncType
from services import S3File
from utils.db import AUser, GroupData
from utils.message.picture import SelfPicture
from utils.message.preprocessor import MentionMe
from utils.saya import build_metadata
from utils.tencentcloud import tcc
from utils.text2image import html2img, md2img

from .crud import (
    ReviewStatus,
    get_all_bottles,
    get_bottle_by_id,
    get_bottles_by_aid,
    get_random_bottle,
    get_self_discuss,
    throw_bottle,
)
from .utils import bottle_md_builder, transform_markdown

channel = Channel.current()
channel.meta = build_metadata(
    func_type=FuncType.fun,
    name="漂流瓶",
    version="1.0",
    description="字面意思，就是漂流瓶",
    cmd_prefix="bottle",
    usage=[
        "发送指令：bottle drop <内容> [-a | --anonymous <是否匿名>] [-r | --remaining <次数>]",
        "发送指令：bottle get",
        "发送指令：bottle check ?<id>",
        "发送指令：bottle delete <id>",
        "发送指令：bottle score <id> <分数>",
        "发送指令：bottle discuss <id> <评论>",
    ],
    options=[
        {"name": "内容", "help": "漂流瓶的内容，可选：文字、图片或混合内容"},
        {"name": "-a", "help": "是否匿名，可选"},
        {"name": "id", "help": "漂流瓶的编号"},
        {"name": "分数", "help": "漂流瓶的评分"},
        {"name": "评论", "help": "漂流瓶的评论"},
    ],
    example=[
        {"run": "bottle drop 你好", "to": "发送一条漂流瓶，内容为“你好”"},
        {"run": "bottle drop 你好 -a -r 10", "to": "发送一条匿名漂流瓶，内容为“你好”，可以被捡 10 次"},
        {"run": "bottle get", "to": "捡一条漂流瓶"},
        {"run": "bottle check 1", "to": "查看编号为 1 的漂流瓶"},
        {"run": "bottle check", "to": "查看自己的漂流瓶"},
        {"run": "bottle delete 1", "to": "删除编号为 1 的漂流瓶"},
        {"run": "bottle score 1 5", "to": "给编号为 1 的漂流瓶评分为 5 分"},
        {"run": "bottle discuss 1 你好", "to": "给编号为 1 的漂流瓶评论“你好”"},
    ],
)


def qrdecode(img: bytes) -> int:
    image = Image.open(BytesIO(img))
    # image_array = np.array(image)
    image_data = pyzbar.decode(image)
    return len(image_data)


@listen(MessageReceived)
@dispatch(Twilight([UnionMatch("bottle", "漂流瓶")], preprocessor=MentionMe()))
async def bottle_handler(ctx: Context, auser: AUser):  # noqa: ANN201
    self_bottle = await get_bottles_by_aid(auser.aid).count()
    self_text = "你还没有丢过漂流瓶哦！" if not self_bottle else f"你共投掷 {self_bottle} 个漂流瓶"
    await ctx.scene.send_message(f"当前池子内共有 {await get_all_bottles().count()} 个漂流瓶，{self_text}")


@listen(MessageReceived)
@dispatch(
    Twilight(
        [
            RegexMatch(
                r"((bottle|漂流瓶)\s+(drop|release|throw|丢(漂流瓶)?|扔(漂流瓶)?|放生(漂流瓶)?))|((丢|扔|放生)(漂流瓶|瓶子))"
            ),
            "arg_remaining" @ ArgumentMatch("-r", "--remaining", default=-1, optional=True),
            "arg_anonymous" @ ArgumentMatch("-a", "--anonymous", action="store_true", optional=True),
            FullMatch("\n", optional=True),
            "arg_anythings" @ WildcardMatch(optional=True).flags(re.S),
        ],
        preprocessor=MentionMe(),
    )
)
async def throw_bottle_handler(  # noqa: ANN201
    ctx: Context,
    group_data: GroupData,
    auser: AUser,
    s3file: S3File,
    arg_remaining: ArgResult,
    arg_anonymous: ArgResult,
    arg_anythings: Annotated[MessageChain, ResultValue()],
):
    remaining = int(str(arg_remaining.result))
    anonymous = bool(arg_anonymous.result)
    # remaining 参数只能为-1或1-1000
    if remaining != -1 and not (1 <= remaining <= 1000):
        return await ctx.scene.send_message("漂流瓶可捡取次数只能为 -1 或 1-1000！")

    text = None
    images: list[Picture] = []
    # 检查是否有内容被加入漂流瓶
    if arg_anythings:
        if arg_anythings.has(Text):
            text = str(MessageChain(arg_anythings.get(Text)).merge())
            if len(text) > 400:
                return await ctx.scene.send_message("你的漂流瓶内容过长（400），开通 ABot 大会员以提高最大长度！")

        if arg_anythings.has(Picture):
            if len(arg_anythings.get(Picture)) > 5:
                return await ctx.scene.send_message("丢漂流瓶只能携带最多 5 张图片哦，开通 ABot 大会员可提高最大数量！")
            images.extend(arg_anythings.get(Picture))

    if not text and not images:
        return await ctx.scene.send_message("不可以丢空漂流瓶哦！")

    await ctx.scene.send_message("正在自动审核漂流瓶内容")
    review_list: list[tuple[int, str, str]] = []
    if text:
        logger.info("[Func.drift_bottle] 正在审核漂流瓶文字")
        try:
            moderation = await tcc.text_moderation(text)
        except Exception:
            return await ctx.scene.send_message("文字审核失败，请稍后重试！")
        if not moderation.is_safe:
            review_list.append((0, moderation.label, moderation.sub_label))

    if images:
        logger.info("[Func.drift_bottle] 正在审核漂流瓶图片")
        for i, image in enumerate(images, 1):
            image_name: str = image.resource.filename  # type: ignore
            image_url: str = image.resource.url  # type: ignore
            if await s3file.object_exists(image_name):
                try:
                    image_response = await s3file.get_object(image_name)
                    image_data = await image_response.read()
                    moderation = await tcc.image_moderation(image_url=image_url, image_id=image_name)
                    await s3file.set_object_tags(
                        image_name,
                        {
                            "image_safe": "1" if moderation.is_safe else "0",
                            "image_label": moderation.label,
                            "image_score": str(moderation.Response.Score),
                        },
                    )
                    if not moderation.is_safe:
                        review_list.append((i, moderation.label, moderation.sub_label))
                    if qrcode_count := qrdecode(image_data) > 0:
                        await s3file.set_object_tags(image_name, {"qr_code": str(qrcode_count)})
                        review_list.append((i, "AD", "QRCode"))
                    await s3file.set_object_tags(image_name, {"drift_bottle": "true"})
                except Exception:
                    logger.exception("[Func.drift_bottle] 图片审核失败")
                    return await ctx.scene.send_message("图片审核失败，请稍后重试！")
            else:
                return await ctx.scene.send_message("图片异常，未加载成功，请稍后重试！")

    # 基础价格和消息
    bottle_price = 2
    price_msg = "漂流瓶价格为 2 个游戏币"

    # 计算额外费用
    if text:
        bottle_price += 1
        price_msg += "，加上文字内容额外 1 个游戏币"
    if images:
        image_cost = len(images) * 3
        bottle_price += image_cost
        price_msg += f"，加上 {len(images)} 张图片额外 {image_cost} 个游戏币"

    # 拼接总价格
    price_msg += f"，总计 {bottle_price} 个游戏币。"

    anonymous_msg = "匿名漂流瓶，" if anonymous else ""

    # 构建剩余捡取次数消息
    remaining_msg = f"可被捡取 {remaining} 次。" if remaining != -1 else "可被无限次捡取。"

    review_msg = ""
    if review_list:
        review_msg = "如下内容审核未通过：\n"
        for i, label, sub_label in review_list:
            if i == 0:
                review_msg += f"文字内容，原因：{label} / {sub_label}\n"
            else:
                review_msg += f"第 {i} 张图片，原因：{label} / {sub_label}\n"
        review_msg += "漂流瓶将进入人工审核"
    else:
        review_msg = "漂流瓶内容审核通过"

    # 处理购买逻辑
    in_bottle = "一段文字和一些图片" if text and images else "一段文字" if text else "一些图片"
    await ctx.scene.send_message(
        f"瓶子里含有：{in_bottle}，该瓶子为{anonymous_msg}售价 {bottle_price} 游戏币，{remaining_msg}\n{review_msg}。\n"
        "请确认无误后发送 “@ABot y” 以确认购买。\n\n请注意：严禁在漂流瓶中发送套娃 Bot 聊天记录等内容，发现后将永久加入漂流瓶黑名单。"
    )

    async def waiter(waiter_ctx: Context, message: MessageChain) -> bool | None:
        if waiter_ctx.client != ctx.client:
            return None
        message_str = str(message.get_first(Text)).removeprefix("/").strip().lower()
        if message_str in ["y", "yes", "是"]:
            return True
        if message_str in ["n", "no", "否"]:
            return False
        await waiter_ctx.scene.send_message("无效输入: 请重新确认")
        return None

    if not await FunctionWaiter(
        waiter,
        [MessageReceived],
        block_propagation=ctx.client.follows("::friend") or ctx.client.follows("::guild.user"),
    ).wait(30, False):
        return await ctx.scene.send_message("投掷漂流瓶已取消")

    if await auser.reduce_coin(bottle_price, group_id=group_data.group_id, source="漂流瓶", detail=price_msg):
        bottle = await throw_bottle(
            auser.aid,
            group_data.group_id,
            text,
            remaining,
            [x.resource.filename for x in images],  # type: ignore
            ReviewStatus.PENDING if review_list else ReviewStatus.AI_APPROVED,
            anonymous=anonymous,
        )
        return await ctx.scene.send_message(
            f"成功购买并丢出漂流瓶！\n瓶子编号：{bottle}" + ("\n漂流瓶正在等待人工审核" if review_list else "")
        )
    return await ctx.scene.send_message(f"游戏币不足，无法丢出漂流瓶。{price_msg}")


@listen(MessageReceived)
@dispatch(
    Twilight(
        [RegexMatch(r"((bottle|漂流瓶)\s+(fish|get|打?捞))|(打?捞(漂流瓶|瓶子))|lplp|l'p'l'p")],
        preprocessor=MentionMe(),
    )
)
async def fish_bottle_handler(ctx: Context, group_data: GroupData, auser: AUser, s3file: S3File):  # noqa: ANN201
    bottle = await get_random_bottle()

    if not bottle:
        return await ctx.scene.send_message("没有漂流瓶可以捡哦！")
    logger.debug(f"[Func.drift_bottle] 捞到的漂流瓶：{bottle.bottle_id}")
    if not await auser.reduce_coin(3, group_id=group_data.group_id, source="漂流瓶", detail="捞瓶子"):
        return await ctx.scene.send_message("你的游戏币不足，无法捞漂流瓶！")

    await bottle.pickup()
    bottle_md = await bottle_md_builder(s3file, bottle)
    htm = transform_markdown(bottle_md)
    # test it now.
    return await ctx.scene.send_message(await SelfPicture().from_data(await html2img(htm, width=600)))


@listen(MessageReceived)
@dispatch(
    Twilight(
        [
            RegexMatch(r"((bottle|漂流瓶)\s+(check|查看?))|(查看?(漂流瓶|瓶子))"),
            "arg_bottle_id" @ WildcardMatch(optional=True),
        ],
        preprocessor=MentionMe(),
    )
)
async def check_bottle_handler(  # noqa: ANN201
    ctx: Context, arg_bottle_id: Annotated[MessageChain, ResultValue()], auser: AUser, s3file: S3File
):
    if arg_bottle_id:
        try:
            bottle_id = int(str(arg_bottle_id))
        except Exception:
            return await ctx.scene.send_message("漂流瓶编号必须是数字！")
        bottle = await get_bottle_by_id(bottle_id)
        if not bottle:
            return await ctx.scene.send_message("没有这个漂流瓶！")
        if bottle.aid != auser.aid:
            return await ctx.scene.send_message("你没有权限查看这个漂流瓶漂流瓶！")
        if bottle.review_status == ReviewStatus.PENDING:
            return await ctx.scene.send_message("漂流瓶正在等待人工审核！")
        if bottle.review_status == ReviewStatus.REJECTED:
            return await ctx.scene.send_message("漂流瓶未通过审核！")

        bottle_md = await bottle_md_builder(s3file, bottle)
        htm = transform_markdown(bottle_md)
        return await ctx.scene.send_message(await SelfPicture().from_data(await html2img(htm, width=600)))

    bottles = get_bottles_by_aid(auser.aid)
    if not await bottles.count():
        return await ctx.scene.send_message("你还没有丢过漂流瓶哦！")

    status = {
        ReviewStatus.PENDING: "⏳",
        ReviewStatus.AI_APPROVED: "🤖",
        ReviewStatus.APPROVED: "🧑‍⚖️",
        ReviewStatus.REJECTED: "❌",
    }
    anonymous = {True: "🎭", False: "👤"}
    markdown = f"# 你共有 {await bottles.count()} 个漂流瓶：\n"
    markdown += "| 编号 | 丢出时间 | 次数(剩余) | 评分 | 状态 | 匿名 |\n"
    markdown += "| --: | :------: | :--------: | :--: | :--: | :--: |\n"
    i = 1
    async for bottle in bottles:
        if i >= 20:
            break
        create_time = bottle.create_time.strftime("%Y-%m-%d %H:%M:%S")
        bottle_score = await bottle.get_score() or "无"
        bottle_status = status[bottle.review_status]
        anonymous_status = anonymous[bottle.anonymous]

        markdown += f"| {bottle.bottle_id} | {create_time} | {bottle.total_pickups}({bottle.remaining_pickups}) | {bottle_score} | {bottle_status} | {anonymous_status} |\n"
    markdown += "\n\n> 你可以使用“查漂流瓶 <编号>”查看漂流瓶的详细信息"
    markdown += "\n\n> 审核状态：⏳ 待审核，🤖 AI审核通过，🧑‍⚖️ 人工审核通过，❌ 审核不通过"

    return await ctx.scene.send_message(await SelfPicture().from_data(await md2img(markdown, width=700)))


@listen(MessageReceived)
@dispatch(
    Twilight(
        [
            RegexMatch(r"((bottle|漂流瓶)\s+(delete|del|删除?))|(删除?(漂流瓶|瓶子))"),
            "arg_bottle_id" @ WildcardMatch(optional=True),
        ],
        preprocessor=MentionMe(),
    )
)
async def delete_bottle_handler(ctx: Context, arg_bottle_id: Annotated[MessageChain, ResultValue()], auser: AUser):  # noqa: ANN201
    if not arg_bottle_id:
        return await ctx.scene.send_message("请输入要删除的漂流瓶编号！")
    try:
        bottle_id = int(str(arg_bottle_id))
    except Exception:
        return await ctx.scene.send_message("漂流瓶编号必须是数字！")

    bottle = await get_bottle_by_id(bottle_id)
    if not bottle:
        return await ctx.scene.send_message("没有这个漂流瓶！")
    if bottle.aid != auser.aid:
        return await ctx.scene.send_message("你没有权限删除这个漂流瓶！")
    await bottle.delete()
    await auser.add_coin(1, source="漂流瓶", detail="删除瓶子")
    return await ctx.scene.send_message("成功删除漂流瓶！返还 1 个游戏币。")


@listen(MessageReceived)
@dispatch(
    Twilight(
        [
            RegexMatch(r"((bottle|漂流瓶)\s+(score|评分))|((漂流瓶|瓶子)评分)"),
            "arg_bottle_id" @ ParamMatch(optional=True),
            "arg_score" @ ParamMatch(optional=True),
        ],
        preprocessor=MentionMe(),
    )
)
async def score_bottle_handler(  # noqa: ANN201
    ctx: Context,
    arg_bottle_id: Annotated[MessageChain, ResultValue()],
    arg_score: Annotated[MessageChain, ResultValue()],
    auser: AUser,
):
    if not arg_bottle_id or not arg_score:
        return await ctx.scene.send_message("请输入要评分的漂流瓶编号和分数！")
    try:
        bottle_id = int(str(arg_bottle_id))
        score = int(str(arg_score))
    except Exception:
        return await ctx.scene.send_message("漂流瓶编号和分数必须是数字！")
    if not (1 <= score <= 5):
        return await ctx.scene.send_message("评分仅可为 1-5 分！")
    bottle = await get_bottle_by_id(bottle_id)
    if not bottle:
        return await ctx.scene.send_message("没有这个漂流瓶！")
    if bottle.aid == auser.aid:
        return await ctx.scene.send_message("你不能给自己的漂流瓶评分！")
    await bottle.score_bottle(auser.aid, score)
    return await ctx.scene.send_message("评分成功！")


@listen(MessageReceived)
@dispatch(
    Twilight(
        [
            RegexMatch(r"((bottle|漂流瓶)\s+(discuss|评论))|((漂流瓶|瓶子)评论)"),
            "arg_bottle_id" @ ParamMatch(optional=True),
            "arg_discuss" @ ParamMatch(optional=True),
        ],
        preprocessor=MentionMe(),
    )
)
async def discuss_bottle_handler(  # noqa: ANN201
    ctx: Context,
    arg_bottle_id: Annotated[MessageChain, ResultValue()],
    arg_discuss: Annotated[MessageChain, ResultValue()],
    auser: AUser,
):
    if not arg_bottle_id or not arg_discuss:
        return await ctx.scene.send_message("请输入要评论的漂流瓶编号和评论内容！")
    try:
        bottle_id = int(str(arg_bottle_id))
    except Exception:
        return await ctx.scene.send_message("漂流瓶编号必须是数字！")
    bottle = await get_bottle_by_id(bottle_id)
    if not bottle:
        return await ctx.scene.send_message("没有这个漂流瓶！")
    if await get_self_discuss(bottle_id, auser.aid).count() >= 3:
        return await ctx.scene.send_message("你已对该漂流瓶发表过 3 条评论，无法再次发送！")
    discuss = str(arg_discuss)
    if not (3 <= len(discuss) <= 500):
        return await ctx.scene.send_message("评论字数需在 3-100 字之间！")
    text_moderation = await tcc.text_moderation(discuss)
    if not text_moderation.is_safe:
        return await ctx.scene.send_message(f"评论内容审核失败：{text_moderation.label} / {text_moderation.sub_label}")
    await bottle.discuss_bottle(auser.aid, discuss)
    return await ctx.scene.send_message("评论成功！")
