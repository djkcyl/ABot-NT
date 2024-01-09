from typing import Annotated

from avilla.core import Context, MessageChain, MessageReceived
from avilla.twilight.twilight import ResultValue, Twilight, UnionMatch, WildcardMatch
from graia.saya import Channel, Saya
from graiax.shortcut import dispatch, listen

from models.saya import FuncItem, FuncType
from utils.db import GroupData
from utils.message.picture import SelfPicture
from utils.message.preprocessor import MentionMe
from utils.saya import build_metadata
from utils.text2image import md2img

channel = Channel.current()
channel.meta = build_metadata(
    func_type=FuncType.core,
    name="帮助",
    version="1.4",
    description="打开帮助菜单",
    cmd_prefix="help",
    usage=["发送指令：help <id>"],
    options=[{"name": "id", "help": "功能的id，填写后会显示该功能的详细帮助信息，可选"}],
    example=[{"run": "help", "to": "打开帮助菜单"}, {"run": "help 1", "to": "打开第一个功能的帮助菜单"}],
    can_be_disabled=False,
)
saya = Saya.current()


@listen(MessageReceived)
@dispatch(
    Twilight([UnionMatch("help", "帮助", "菜单", "功能"), "func_id" @ WildcardMatch(optional=True)], preprocessor=MentionMe())
)
async def main_menu(  # noqa: ANN201
    ctx: Context,
    group_data: GroupData,
    func_id: Annotated[MessageChain, ResultValue()],
):
    """
    主菜单功能，显示插件的功能列表。

    参数:
        app: Ariadne实例
        group: 群组
        group_data: 群组数据模型
        func_id: 功能ID的信息链
    """
    # 获取所有未隐藏的功能列表
    func_list: list[tuple[str, FuncItem]] = [
        (func, FuncItem(**channel.meta)) for func, channel in saya.channels.items() if not channel.meta["hidden"]
    ]
    # 按照功能类型和名称排序
    func_list.sort(key=lambda x: (x[1].func_type, x[0]))

    # 如果有指定功能ID，则显示该功能的详细帮助信息
    if func_want := str(func_id):
        # 查找指定功能
        func, meta = await find_function(func_list, func_want)

        # 如果该功能已被关闭或正在维护，则返回提示信息
        if not func or not meta or func in group_data.disable_functions or meta.maintain:
            return await ctx.scene.send_message("该功能已被本群管理员关闭或正在维护")

        # 构建帮助信息字符串
        help_str = f"# {meta.name} v{meta.version}\n\n> {func}\n\n{meta.description}"
        if meta.usage:
            help_str += "\n\n### 使用方法\n" + "\n".join(f"- {usage}" for usage in meta.usage)
        if meta.options:
            help_str += "\n\n### 可用参数\n" + "\n".join(
                f"- `{option['name']}`: {option['help']}" for option in meta.options
            )
        if meta.example:
            help_str += "\n\n### 示例\n" + "\n".join(
                f"- `{example['run']}`: {example['to']}" for example in meta.example
            )
        if meta.tips:
            help_str += "\n\n### 提示\n" + "\n".join(f"- {tip}" for tip in meta.tips)
        # 将帮助信息字符串转换为图片并发送到群组
        return await ctx.scene.send_message(await SelfPicture().from_data(await md2img(help_str)))

    # 如果没有指定功能ID，则显示主菜单
    help_str = (
        f"# ABot 功能菜单\n### （{group_data.group_id}）\n"
        "| ID | 状态 | 插件分类 | 名称 | 指令前缀 | 介绍 | 版本 |\n"
        "| --: | :---: | :-------: | ------- | :------- | ------- | :--- |\n"
    )

    for i, (func, meta) in enumerate(func_list, start=1):
        # 如果该功能已被关闭或正在维护，则在状态栏显示关闭或维护
        if func in group_data.disable_functions:
            status = "🔴"
        elif meta.maintain:
            status = "🚫"
        else:
            status = "🟢"
        # 构建主菜单信息字符串
        help_str += (
            f"| {i} | {status} | {meta.func_type.value} | {meta.name} | {meta.cmd_prefix} | {meta.description} | v{meta.version} |\n"
        )
    help_str += (
        "\n- 详细查看功能使用方法请发送 help <功能id>，例如：help 1"
        # "\n- 管理员可发送 开启功能/关闭功能 <功能id> 来开启/关闭某个功能"
        "\n- 在频道和群内使用 ABot 需要 @ABot 才能让 ABot 响应哦"
        "\n- 群内使用 ABot 时，ABot 无法收到 At 他人的消息，如有需要指定他人的功能，请使用对方的 aid 来替代 At"
        "\n- 可以使用 `/mydata` 来检查自己的 aid"
        "\n- 本菜单由 ABot 功能 help 自动生成，如有问题请联系开发者"
        "\n- 更多新老功能正在开发移植中，敬请期待！（老 ABot 的功能大多数都会迁移的）"
    )
    # 将主菜单信息字符串转换为图片并发送到群组
    return await ctx.scene.send_message(
        await SelfPicture().from_data(await md2img(help_str.replace("<", "&lt;").replace(">", "&gt;"), 1000)),
    )


async def find_function(func_list: list[tuple[str, FuncItem]], func_want: str) -> tuple[str, FuncItem] | tuple[None, None]:
    """
    在功能列表中查找指定功能。

    参数:
        func_list: 功能列表
        func_want: 指定的功能名称或ID

    返回值:
        如果找到指定功能，则返回该功能的名称和元数据；否则返回None。
    """
    # 如果指定功能为数字，则按照ID查找
    if func_want.isdigit():
        func_index = int(func_want) - 1
        if func_index < 0 or func_index >= len(func_list):
            return None, None
        return func_list[func_index]

    # 否则按照名称查找
    for func, meta in func_list:
        if func == func_want:
            return func, meta
    return None, None
