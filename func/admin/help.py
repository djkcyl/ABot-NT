from typing import Annotated

from avilla.core import Context, MessageChain, MessageReceived
from avilla.twilight.twilight import RegexMatch, ResultValue, Twilight, WildcardMatch
from graia.saya import Channel, Saya
from graiax.shortcut import dispatch, listen

from utils.message.picture import SelfPicture
from utils.message.preprocessor import MentionMe
from utils.saya import build_metadata
from utils.saya.model import FuncItem, FuncType, GroupData
from utils.text2image import md2img

channel = Channel.current()
channel.meta = build_metadata(
    func_type=FuncType.core,
    name="帮助",
    version="1.3",
    description="打开帮助菜单",
    usage=["发送指令：help <id>"],
    options=[{"name": "id", "help": "功能的id，填写后会显示该功能的详细帮助信息，可选"}],
    example=[{"run": "help", "to": "打开帮助菜单"}, {"run": "help 1", "to": "打开第一个功能的帮助菜单"}],
    can_be_disabled=False,
)
saya = Saya.current()


@listen(MessageReceived)
@dispatch(Twilight([RegexMatch(r"[./]?(help|帮助|菜单)"), "func_id" @ WildcardMatch()], preprocessor=MentionMe()))
async def main_menu(
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
        help_str = f"# {meta.name} v{meta.version}\n\n> {func}\n\n{meta.description}" f"\n\n### 使用方法\n" + (
            "\n".join(f"- {usage}" for usage in meta.usage) if meta.usage else ""
        ) + "\n\n### 可用参数\n" + (
            "\n".join(f"- `{option['name']}`: {option['help']}" for option in meta.options) if meta.options else ""
        ) + "\n\n### 示例\n" + (
            "\n".join(f"- `{example['run']}`: {example['to']}" for example in meta.example) if meta.example else ""
        )
        # 将帮助信息字符串转换为图片并发送到群组
        return await ctx.scene.send_message(await SelfPicture().from_data(await md2img(help_str)))
    else:
        # 如果没有指定功能ID，则显示主菜单
        help_str = (
            f"# ABot 群菜单\n### 群名（{group_data.group_id}）\n"
            "| ID | 状态 | 插件分类 | 功能名称 | 版本 |\n"
            "| --: | :---: | :-------: | ------- | --- |\n"
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
            help_str += f"| {i} | {status} | {meta.func_type.value} | {meta.name} | v{meta.version} |\n"
        help_str += (
            "\n- 详细查看功能使用方法请发送 help <功能id>，例如：help 1"
            # "\n- 管理员可发送 开启功能/关闭功能 <功能id> 来开启/关闭某个功能"
            "\n- 在频道和群内使用 ABot 需要 @ABot 才能让 ABot 响应哦"
        )
        # 将主菜单信息字符串转换为图片并发送到群组
        await ctx.scene.send_message(
            await SelfPicture().from_data(await md2img(help_str.replace("<", "&lt;").replace(">", "&gt;"))),
        )


async def find_function(func_list: list[tuple[str, FuncItem]], func_want: str):
    """
    在功能列表中查找指定功能。

    参数:
        func_list: 功能列表
        func_want: 指定的功能名称或ID

    返回值:
        如果找到指定功能，则返回该功能的名称和元数据；否则返回None。
    """
    try:
        return next(filter(lambda x: x[1].name == func_want, func_list))
    except StopIteration:
        try:
            return func_list[int(func_want) - 1]
        except (IndexError, ValueError):
            return None, None
